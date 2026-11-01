from collections import defaultdict
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Callable, ClassVar, Dict, List, Tuple
import copy
import os
import re
import shutil
import threading
import uuid

import msgspec
import rapidjson as json

from Backend.core.config import ConfigMixin
from Backend.core.paths import project_cache_root
from Backend.domain.config.task_type import TaskType
from Backend.core.log import LogMixin
from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_item import CacheItem, TranslationStatus
from Backend.domain.models.cache_project import CacheProject, CacheProjectStatistics
from Backend.domain.models.intermediate import (
    SCHEMA_VERSION, generate_item_chunks, generate_previous_chunks, normalize_project,
    parse_model,
)


def copy_legacy_extras(content: dict) -> dict:
    """Keep old extension fields when upgrading an unversioned JSON cache."""
    result = copy.deepcopy(content)

    def preserve_unknown(node, model):
        known = {field.name for field in fields(model)}
        extra = node.setdefault("extra", {})
        if not isinstance(extra, dict):
            raise ValueError("缓存 extra 必须为对象")
        for key in list(node):
            if key not in known:
                value = node.pop(key)
                if key in extra and extra[key] != value:
                    extra.setdefault("legacy_fields", {})[key] = value
                else:
                    extra[key] = value

    preserve_unknown(result, CacheProject)
    for file in result.get("files", {}).values():
        preserve_unknown(file, CacheFile)
        for item in file.get("items", []):
            preserve_unknown(item, CacheItem)
            # Early Trans/TPP caches can contain numeric spreadsheet cells.
            item.update(CacheItem.from_dict(item).to_dict())
    return result


class CacheManager(ConfigMixin, LogMixin):
    """缓存管理器，负责项目缓存的读写、历史扫描与内存态更新。"""

    ANALYSIS_EXTRA_KEY = "analysis_v1"
    SAVE_INTERVAL = 8  # 缓存保存间隔（秒）
    CACHE_FILENAME = "AinieeCacheData.json"
    STATS_FILENAME = "ProjectStatistics.json"
    HISTORY_LIMIT = 3
    CACHE_WRITE_LOCK: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, on_saved: Callable[[dict], None] | None = None) -> None:
        # 线程锁：保护 project 的读写以及缓存落盘过程
        self.file_lock = threading.Lock()
        self.project = None
        self.on_saved = on_saved
        self._save_thread = None
        self._save_stop_event = threading.Event()
        self._save_requested = threading.Event()
        self._save_lifecycle_lock = threading.RLock()
        self._closed = False

    def start_saving(self) -> None:
        """显式启动周期保存；重复启动不会创建额外线程。"""
        with self._save_lifecycle_lock:
            if self._closed:
                raise RuntimeError("缓存管理器已关闭")
            if self._save_thread is not None and self._save_thread.is_alive():
                return
            self._save_stop_event.clear()
            self._save_thread = threading.Thread(
                target=self.save_to_file_tick, name="cache-saving", daemon=True,
            )
            self._save_thread.start()

    def stop_saving(self) -> None:
        """停止周期保存并等待正在进行的写盘完成；之后可以重新启动。"""
        with self._save_lifecycle_lock:
            self._save_stop_event.set()
            thread = self._save_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        with self._save_lifecycle_lock:
            if self._save_thread is thread and (thread is None or not thread.is_alive()):
                self._save_thread = None

    def close(self) -> None:
        """结束保存生命周期并冲刷尚未写盘的数据。"""
        with self._save_lifecycle_lock:
            self._closed = True
        self.stop_saving()
        if self._save_requested.is_set():
            self.save_to_file()

    # 获取缓存目录相关路径
    @classmethod
    def get_project_cache_root(cls) -> str:
        """获取项目缓存根目录。"""
        return str(project_cache_root())

    @classmethod
    def get_project_cache_dir(cls, project_id: str) -> str:
        """根据 project_id 获取对应项目缓存目录。"""
        if not project_id:
            raise ValueError("project_id is required")
        return os.path.join(cls.get_project_cache_root(), project_id)

    @classmethod
    def get_default_cache_path(cls, output_path: str = "", project_id: str = "") -> str:
        """获取缓存文件路径。

        优先走新的 ProjectCache/<project_id>/AinieeCacheData.json；
        output_path 仅保留给旧调用方和旧缓存兼容读取使用。
        """
        if project_id:
            return os.path.join(cls.get_project_cache_dir(project_id), cls.CACHE_FILENAME)

        if output_path:
            if os.path.isfile(output_path):
                return output_path

            direct_cache_path = os.path.join(output_path, cls.CACHE_FILENAME)
            if os.path.isfile(direct_cache_path):
                return direct_cache_path

            legacy_cache_path = os.path.join(output_path, "cache", cls.CACHE_FILENAME)
            if os.path.isfile(legacy_cache_path):
                return legacy_cache_path

        histories = cls.list_project_histories(limit=1, prune=False)
        if histories:
            return histories[0]["cache_path"]

        return os.path.join(cls.get_project_cache_root(), cls.CACHE_FILENAME)

    @classmethod
    def get_project_statistics_path(cls, project_id: str) -> str:
        """获取项目统计文件路径。"""
        return os.path.join(cls.get_project_cache_dir(project_id), cls.STATS_FILENAME)

    # 基础数据整理辅助方法
    @classmethod
    def read_project_statistics(cls, project_id: str) -> dict | None:
        """Read ProjectStatistics.json for the given project."""
        if not project_id:
            return None
        return cls._read_statistics_payload(cls.get_project_statistics_path(project_id))

    @classmethod
    def _get_now_iso(cls) -> str:
        return datetime.now().isoformat(timespec="seconds")

    @classmethod
    def _timestamp_to_iso(cls, timestamp) -> str:
        if timestamp is None:
            return cls._get_now_iso()
        return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")

    @staticmethod
    def _parse_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_progress(
        cls,
        project: CacheProject,
        stats_payload: dict | None,
    ) -> tuple[int, int, bool]:
        """统一规范化项目进度数据。

        优先使用 project.stats_data，其次回退到统计文件中的 total_line / line。
        """
        total_line = 0
        line = 0

        if isinstance(stats_payload, dict):
            total_line = cls._parse_int(stats_payload.get("total_line", 0))
            line = cls._parse_int(stats_payload.get("line", 0))

        if project.stats_data is not None:
            total_line = cls._parse_int(project.stats_data.total_line or total_line)
            line = cls._parse_int(project.stats_data.line or line)
        elif total_line or line:
            project.stats_data = CacheProjectStatistics(total_line=total_line, line=line)
            return total_line, line, True

        return total_line, line, False

    @classmethod
    def _build_stats_payload(
        cls,
        project: CacheProject,
        stats_payload: dict | None = None,
    ) -> dict:
        """构建写入 ProjectStatistics.json 的内容。"""
        total_line, line, _ = cls._normalize_progress(project, stats_payload)
        return {
            "project_id": project.project_id,
            "project_name": project.project_name,
            "project_create_time": project.project_create_time,
            "total_line": total_line,
            "line": line,
        }

    @classmethod
    def _ensure_project_metadata(
        cls,
        project: CacheProject,
        fallback_project_id: str = "",
        fallback_create_time: str = "",
    ) -> bool:
        """补齐项目基础元数据，返回值表示对象是否被修改。"""
        changed = False

        if not project.project_id:
            project.project_id = fallback_project_id or uuid.uuid4().hex
            changed = True

        if not project.project_create_time:
            project.project_create_time = fallback_create_time or cls._get_now_iso()
            changed = True

        return changed

    @classmethod
    def _write_project_cache_files(cls, project: CacheProject) -> None:
        """将项目缓存和统计信息原子写入 ProjectCache/<project_id>/ 目录。"""
        cls._ensure_project_metadata(project)
        normalize_project(project)

        cache_dir = cls.get_project_cache_dir(project.project_id)
        cache_path = os.path.join(cache_dir, cls.CACHE_FILENAME)
        stats_path = os.path.join(cache_dir, cls.STATS_FILENAME)
        cache_tmp_path = cache_path + f".{os.getpid()}.tmp"
        stats_tmp_path = stats_path + f".{os.getpid()}.tmp"

        with cls.CACHE_WRITE_LOCK:
            try:
                os.makedirs(cache_dir, exist_ok=True)

                cls._backup_legacy_cache(cache_path)

                # 先写临时文件，再 replace，避免读到半截文件
                content_bytes = msgspec.json.encode(project.to_dict())
                with open(cache_tmp_path, "wb") as writer:
                    writer.write(content_bytes)
                os.replace(cache_tmp_path, cache_path)

                # 统计文件单独保存，供启动页快速读取项目概况
                stats_payload = cls._build_stats_payload(project)
                with open(stats_tmp_path, "w", encoding="utf-8") as writer:
                    json.dump(stats_payload, writer, ensure_ascii=False, indent=4)
                os.replace(stats_tmp_path, stats_path)
            finally:
                # 确保异常情况下临时文件也会被清理
                for tmp_path in (cache_tmp_path, stats_tmp_path):
                    if not os.path.exists(tmp_path):
                        continue
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    @classmethod
    def _read_statistics_payload(cls, stats_path: str) -> dict | None:
        """读取统计文件，读取失败时返回 None。"""
        if not os.path.isfile(stats_path):
            return None

        try:
            if os.path.getsize(stats_path) == 0:
                return None

            with open(stats_path, "r", encoding="utf-8") as reader:
                content = reader.read().strip()

            if not content:
                return None

            payload = json.loads(content)
            if isinstance(payload, dict):
                return payload
            return None
        except (json.JSONDecodeError, OSError, IOError):
            return None

    @classmethod
    def _build_history_entry_from_stats(
        cls,
        cache_dir: str,
        cache_path: str,
        stats_path: str,
        stats_payload: dict,
    ) -> dict:
        """Build a lightweight history entry from ProjectStatistics.json."""
        dir_name = os.path.basename(cache_dir)
        project_id = str(stats_payload.get("project_id", "") or dir_name).strip() or dir_name
        project_name = str(stats_payload.get("project_name", "") or project_id).strip() or project_id
        project_create_time = str(stats_payload.get("project_create_time", "")).strip() or cls._timestamp_to_iso(
            os.path.getctime(cache_dir)
        )
        total_line = cls._parse_int(stats_payload.get("total_line", 0))
        line = cls._parse_int(stats_payload.get("line", 0))

        return {
            "project_id": project_id,
            "project_name": project_name,
            "project_create_time": project_create_time,
            "total_line": total_line,
            "line": line,
            "is_complete": total_line > 0 and line >= total_line,
            "cache_dir": cache_dir,
            "cache_path": cache_path,
            "stats_path": stats_path,
        }

    @classmethod
    def list_project_histories(cls, limit: int | None = None, prune: bool = False) -> list[dict]:
        """扫描 ProjectCache 目录并返回历史项目列表。

        未指定 limit 时使用后端的 HISTORY_LIMIT，显式传入 0 时不限数量。
        会按创建时间倒序排序；prune=True 时会清理无效目录和超出限制的旧项目。
        """
        if limit is None:
            limit = cls.HISTORY_LIMIT
        cache_root = cls.get_project_cache_root()
        os.makedirs(cache_root, exist_ok=True)

        histories = []
        invalid_project_ids = []

        for entry in os.scandir(cache_root):
            if not entry.is_dir():
                continue

            stats_path = os.path.join(entry.path, cls.STATS_FILENAME)
            if not os.path.isfile(stats_path):
                continue

            cache_path = os.path.join(entry.path, cls.CACHE_FILENAME)
            if not os.path.isfile(cache_path):
                invalid_project_ids.append(entry.name)
                continue

            stats_payload = cls._read_statistics_payload(stats_path)
            if not isinstance(stats_payload, dict):
                invalid_project_ids.append(entry.name)
                continue

            histories.append(
                cls._build_history_entry_from_stats(
                    entry.path,
                    cache_path,
                    stats_path,
                    stats_payload,
                )
            )

        if prune:
            for project_id in invalid_project_ids:
                cls.delete_project_cache(project_id)

        # 按项目创建时间倒序排列，最新项目排在最前
        histories.sort(
            key=lambda item: (item.get("project_create_time", ""), item.get("project_id", "")),
            reverse=True,
        )

        if limit > 0 and len(histories) > limit:
            if prune:
                # 超过上限时删除更旧的项目缓存
                for stale_history in histories[limit:]:
                    cls.delete_project_cache(stale_history["project_id"])
                histories = histories[:limit]
                return histories

            histories = histories[:limit]

        return histories

    @classmethod
    def delete_project_cache(cls, project_id: str) -> bool:
        """删除指定项目缓存目录。"""
        if not project_id:
            return False

        cache_root = Path(cls.get_project_cache_root()).resolve()
        target_path = Path(cls.get_project_cache_dir(project_id)).resolve()

        try:
            # 删除前校验目标路径确实位于 ProjectCache 根目录下
            if os.path.commonpath([str(cache_root), str(target_path)]) != str(cache_root):
                return False
        except ValueError:
            return False

        if not target_path.exists():
            return False

        try:
            shutil.rmtree(target_path, ignore_errors=False)
            return True
        except OSError:
            return False

    # 保存与加载
    def save_to_file(self) -> dict | None:
        """同步保存当前项目；失败抛出异常，通知回调不影响写盘结果。"""
        # Clear before writing so a concurrent mutation can request another
        # snapshot without its dirty flag being erased after this write.
        self._save_requested.clear()
        try:
            with self.file_lock:
                if self.project is None:
                    return None
                self._ensure_project_metadata(self.project)
                self._write_project_cache_files(self.project)
                saved = {
                    "project_id": self.project.project_id,
                    "cache_path": self.get_default_cache_path(project_id=self.project.project_id),
                }
        except Exception:
            self._save_requested.set()
            raise
        if self.on_saved:
            try:
                self.on_saved(saved)
            except Exception as error:
                self.warning(f"项目缓存已保存，但保存通知失败：{error}")
        return saved

    def save(self) -> dict | None:
        return self.save_to_file()

    def save_to_file_tick(self) -> None:
        """定时保存任务。"""
        while not self._save_stop_event.wait(self.SAVE_INTERVAL):
            if self._save_requested.is_set():
                try:
                    self.save_to_file()
                except Exception as error:
                    self.error(f"定时保存项目缓存失败，将在下一周期重试：{error}", error)

    def require_save_to_file(self, output_path: str | None = None) -> None:
        """请求保存缓存。output_path 参数仅保留兼容。"""
        self._save_requested.set()

    def load_from_project(self, data: CacheProject):
        """直接从内存中的 CacheProject 对象加载项目。"""
        self._ensure_project_metadata(data)
        self.project = normalize_project(data)

    def load_from_project_id(self, project_id: str) -> None:
        """根据 project_id 从新的 ProjectCache 目录加载项目。"""
        path = self.get_default_cache_path(project_id=project_id)
        with self.file_lock:
            if os.path.isfile(path):
                self.project = self.read_from_file(path)
            else:
                self.project = None

    def load_from_file(self, output_path: str = "") -> None:
        """兼容旧调用方的按路径加载接口。"""
        path = self.get_default_cache_path(output_path=output_path)
        with self.file_lock:
            if os.path.isfile(path):
                self.project = self.read_from_file(path)
            else:
                self.project = None

    @classmethod
    def read_from_file(cls, cache_path) -> CacheProject:
        """Load v2 or migrate an old cache in place with an untouched backup."""
        cache_path = Path(cache_path)
        with cls.CACHE_WRITE_LOCK:
            content_bytes = cache_path.read_bytes()
            content = json.loads(content_bytes.decode("utf-8-sig"))
            if isinstance(content, list):
                project = cls._read_from_old_content(content)
                payload = normalize_project(project).to_dict()
            elif isinstance(content, dict):
                payload = copy_legacy_extras(content) if "schema_version" not in content else content
            else:
                raise ValueError("缓存根节点必须为对象或旧版列表")
            project = parse_model(payload)
            normalized = project.to_dict()
            if normalized != content:
                cls._backup_legacy_cache(cache_path, content_bytes)
                temporary = cache_path.with_name(cache_path.name + f".{os.getpid()}.tmp")
                try:
                    temporary.write_bytes(msgspec.json.encode(normalized))
                    os.replace(temporary, cache_path)
                finally:
                    temporary.unlink(missing_ok=True)
            return project

    @classmethod
    def _backup_legacy_cache(cls, cache_path, content_bytes=None):
        """Preserve the pre-v2 bytes once; caller holds CACHE_WRITE_LOCK."""
        cache_path = Path(cache_path)
        if not cache_path.exists():
            return
        original = cache_path.read_bytes() if content_bytes is None else content_bytes
        content = json.loads(original.decode("utf-8-sig"))
        if isinstance(content, dict) and content.get("schema_version") == SCHEMA_VERSION:
            return
        backup = cache_path.with_name(cache_path.name + ".pre-v2.bak")
        try:
            with backup.open("xb") as writer:
                writer.write(original)
        except FileExistsError:
            pass

    @classmethod
    def _read_from_old_content(cls, content: list) -> CacheProject:
        """兼容旧版列表结构缓存。"""
        if not content or not isinstance(content[0], dict):
            raise ValueError("旧版缓存缺少项目元数据")
        data_iter = iter(content)
        project_data = next(data_iter)
        init_data = {
            "project_id": project_data.get("project_id", ""),
            "project_type": project_data.get("project_type", ""),
            "project_name": project_data.get("project_name", ""),
            "project_create_time": project_data.get("project_create_time", ""),
            "input_path": project_data.get("input_path", ""),
            "extra": copy.deepcopy(project_data.get("extra", {})),
        }
        CacheProject().detected_line_ending

        if "data" in project_data:
            init_data["stats_data"] = CacheProjectStatistics.from_dict(project_data["data"])
        if "file_encoding" in project_data:
            init_data["detected_encoding"] = project_data["file_encoding"]
        if "line_ending" in project_data:
            init_data["detected_line_ending"] = project_data["line_ending"]

        files_props = {}
        new_item_fields = set(fld.name for fld in fields(CacheItem))
        # 这些属性旧版本挂在 item 上，现在要回填到 file 上
        file_extra_keys = {"subtitle_title", "top_text"}
        file_prop_keys = {"file_project_type"}

        for old_item in data_iter:
            storage_path = old_item["storage_path"]
            if storage_path not in files_props:
                files_props[storage_path] = {
                    "items": [],
                    "extra": {},
                    "file_project_type": project_data.get("project_type", ""),
                    "storage_path": storage_path,
                }

            new_item = CacheItem.from_dict(old_item)
            for key, value in old_item.items():
                if key in {"file_name", "polished_text"}:
                    continue
                if key not in new_item_fields:
                    if key in file_prop_keys:
                        files_props[storage_path][key] = value
                    elif key in file_extra_keys:
                        files_props[storage_path]["extra"][key] = value
                    else:
                        new_item.set_extra(key, value)

            files_props[storage_path]["items"].append(new_item)

        init_data["files"] = {key: CacheFile(**value) for key, value in files_props.items()}
        return CacheProject(**init_data)

    # 项目统计与状态判断
    def get_item_count(self) -> int:
        """获取缓存内全部文本条目数量。"""
        if not hasattr(self, "project") or self.project is None:
            return 0
        return self.project.count_items()

    def get_item_count_by_status(self, status: int) -> int:
        """获取指定翻译状态的条目数量。"""
        if not self.project:
            return 0
        return self.project.count_items(status)

    def get_continue_status(self) -> bool:
        """检查项目是否处于“可继续翻译”的状态。"""
        if not self.project:
            return False

        has_translated = False
        has_untranslated = False
        for item in self.project.items_iter():
            status = item.translation_status
            if status == TranslationStatus.TRANSLATED:
                has_translated = True
            elif status == TranslationStatus.UNTRANSLATED:
                has_untranslated = True
            if has_translated and has_untranslated:
                return True
        return has_translated and has_untranslated

    def reset_project_status(self, task_mode: int) -> int:
        """回退已译状态并解除目标语言绑定，允许新任务改用其他目标语言。"""
        if task_mode != TaskType.TRANSLATION:
            raise ValueError("仅支持重置项目的已翻译状态")
        if not self.project:
            return 0

        changed_count = 0
        with self.file_lock:
            for file in self.project.files.values():
                for item in file.items:
                    with item.atomic_scope():
                        if item.translation_status not in (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED):
                            continue
                        item.translation_status = TranslationStatus.UNTRANSLATED

                        changed_count += 1

            # A cancelled/failed first batch can bind a target without producing
            # any translated items. Explicit reset must also release that binding.
            previous_target = self.project.translation_context.pop("target_language", None)
            reset = changed_count > 0 or bool(previous_target)
            if reset:
                self.project.stats_data = CacheProjectStatistics()

        if reset:
            self.save_to_file()
        return changed_count

    # 任务分片生成
    def generate_previous_chunks(
        self,
        all_items: list[CacheItem],
        previous_item_count: int,
        start_idx: int,
    ) -> List[CacheItem]:
        """根据当前片段起点生成上文片段。"""
        return generate_previous_chunks(all_items, previous_item_count, start_idx)

    def generate_item_chunks(
        self,
        limit_type: str,
        limit_count: int,
        previous_line_count: int,
    ) -> Tuple[List[List[CacheItem]], List[List[CacheItem]], List[str]]:
        """按限制条件生成待翻译片段。"""
        return generate_item_chunks(self.project, limit_type, limit_count, previous_line_count)

    # 缓存内容访问与更新
    def get_file_hierarchy(self) -> Dict[str, List[str]]:
        """按目录层级返回缓存中的文件列表。"""
        hierarchy = defaultdict(list)
        if not self.project or not self.project.files:
            return {}

        with self.file_lock:
            for file_path in self.project.files.keys():
                # split 后得到 (目录, 文件名)
                directory, filename = os.path.split(file_path)
                if not directory:
                    directory = "."
                hierarchy[directory].append(filename)

        for dir_path in hierarchy:
            hierarchy[dir_path].sort()

        return dict(hierarchy)

    def update_item_text(self, storage_path: str, text_index: int, field_name: str, new_text: str) -> None:
        """更新缓存中指定文本项的原文或译文。"""
        with self.file_lock:
            cache_file = self.project.get_file(storage_path)
            if not cache_file:
                print(f"Error: 找不到文件 {storage_path}")
                return

            item_to_update = cache_file.get_item(text_index)
            if field_name == "source_text":
                if new_text and new_text.strip() and item_to_update.source_text != new_text:
                    item_to_update.source_text = new_text
            elif field_name == "translated_text":
                # 空译文会把状态回退为未翻译
                item_to_update.translated_text = new_text
                if not new_text or not new_text.strip():
                    item_to_update.translation_status = TranslationStatus.UNTRANSLATED
                else:
                    item_to_update.translation_status = TranslationStatus.TRANSLATED

    def update_generated_translation(
        self,
        storage_path: str,
        text_index: int,
        new_text: str,
        translation_status: int,
    ) -> None:
        """更新任务生成的译文，并保留调用方指定的状态。"""
        with self.file_lock:
            cache_file = self.project.get_file(storage_path)
            if not cache_file:
                print(f"Error: 找不到文件 {storage_path}")
                return

            item_to_update = cache_file.get_item(text_index)
            item_to_update.translated_text = new_text
            if not new_text or not new_text.strip():
                item_to_update.translation_status = TranslationStatus.UNTRANSLATED
            else:
                item_to_update.translation_status = translation_status

    def search_items(self, query: str, scope: str, is_regex: bool, search_flagged: bool) -> list:
        """在整个项目缓存中搜索条目。"""
        results = []
        fields_to_check = ["source_text", "translated_text"] if scope == "all" else [scope]

        try:
            if is_regex:
                # 预编译正则表达式以提高效率
                regex = re.compile(query)
                matcher = lambda text: regex.search(text)
            else:
                matcher = lambda text: query in text
        except re.error as error:
            self.error(f"无效的正则表达式: {error}")
            return []

        with self.file_lock:
            for file_path, cache_file in self.project.files.items():
                for item_index, item in enumerate(cache_file.items):
                    if search_flagged:
                        # 仅返回被语言检查等流程标记过的条目
                        is_item_flagged = False
                        if item.extra:
                            if scope in {"translated_text", "all"}:
                                is_item_flagged = item.extra.get("language_mismatch_translation", False)
                        if not is_item_flagged:
                            continue

                    if not query.strip():
                        # 空查询仅在“只看标记项”时有意义
                        if search_flagged:
                            results.append((file_path, item_index + 1, item))
                        continue

                    for field_name in fields_to_check:
                        text_to_check = getattr(item, field_name, None)
                        if text_to_check and matcher(text_to_check):
                            results.append((file_path, item_index + 1, item))
                            break

        return results

    def get_all_source_items(self) -> list:
        """获取全部有效原文及其文件路径。"""
        all_items_data = []
        with self.file_lock:
            for file_path, cache_file in self.project.files.items():
                for item in cache_file.items:
                    if item.source_text and item.source_text.strip():
                        all_items_data.append(
                            {
                                "source_text": item.source_text,
                                "file_path": file_path,
                            }
                        )
        return all_items_data

    def generate_analysis_source_chunks(self, limit_type: str, limit_count: int) -> List[List[dict]]:
        """生成分析页使用的原文分片。"""
        chunks = []
        if not self.project:
            return chunks

        for file in self.project.files.values():
            current_chunk, current_length = [], 0

            for item in file.items:
                if not item.source_text or not item.source_text.strip():
                    continue

                item_length = item.get_token_count(item.source_text) if limit_type == "token" else 1
                if current_chunk and (current_length + item_length > limit_count):
                    chunks.append(current_chunk)
                    current_chunk, current_length = [], 0

                current_chunk.append(
                    {
                        "text_index": item.text_index,
                        "source_text": item.source_text,
                    }
                )
                current_length += item_length

            if current_chunk:
                chunks.append(current_chunk)

        return chunks

    # 分析页附加数据读写
    def get_analysis_data(self) -> dict:
        """获取分析结果附加数据。"""
        if not self.project:
            return {}
        return self.project.get_extra(self.ANALYSIS_EXTRA_KEY, {}) or {}

    def set_analysis_data(self, analysis_data: dict) -> None:
        """写入分析结果附加数据。"""
        if not self.project:
            return
        self.project.set_extra(self.ANALYSIS_EXTRA_KEY, analysis_data or {})

    def clear_analysis_data(self) -> None:
        """清除分析结果附加数据。"""
        if not self.project:
            return
        self.project.extra.pop(self.ANALYSIS_EXTRA_KEY, None)
