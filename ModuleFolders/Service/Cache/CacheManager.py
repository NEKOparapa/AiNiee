from collections import defaultdict
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Dict, List, Tuple
import os
import re
import shutil
import threading
import time
import uuid

import msgspec
import rapidjson as json

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import CacheProject, CacheProjectStatistics


class CacheManager(ConfigMixin, LogMixin, Base):
    """缓存管理器，负责项目缓存的读写、历史扫描与内存态更新。"""

    ANALYSIS_EXTRA_KEY = "analysis_v1"
    SAVE_INTERVAL = 8  # 缓存保存间隔（秒）
    CACHE_ROOT_NAME = "ProjectCache"
    CACHE_FILENAME = "AinieeCacheData.json"
    STATS_FILENAME = "ProjectStatistics.json"
    HISTORY_LIMIT = 3
    CACHE_WRITE_LOCK: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        super().__init__()

        # 线程锁：保护 project 的读写以及缓存落盘过程
        self.file_lock = threading.Lock()
        self.project = None
        self.save_to_file_stop_flag = False
        self.save_to_file_require_flag = False

        # 注册事件：启动任务时开启定时保存，关闭应用时停止保存线程
        self.subscribe(Base.EVENT.TASK_START, self.start_interval_saving)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)
        self.subscribe(Base.EVENT.TASK_MANUAL_SAVE_CACHE, self.on_manual_save_cache_requested)

    def start_interval_saving(self, event: int, data: dict):
        """启动定时保存；继续任务前先把当前项目状态保存并重新载入。"""
        if data.get("continue_status") is True and self.project:
            current_project_id = self.project.project_id
            self.save_to_file()
            if current_project_id:
                self.load_from_project_id(current_project_id)

        self.save_to_file_stop_flag = False
        threading.Thread(target=self.save_to_file_tick, daemon=True).start()

    def app_shut_down(self, event: int, data: dict) -> None:
        """应用关闭时通知保存线程停止。"""
        self.save_to_file_stop_flag = True

    def on_manual_save_cache_requested(self, event: int, data: dict) -> None:
        """处理手动保存缓存请求。"""
        if self.project is None:
            self.warning("手动保存项目缓存失败：项目数据尚未加载。")
            return

        self.save_to_file()
        self.info("项目缓存文件已通过手动请求保存。")

    # 获取缓存目录相关路径
    @classmethod
    def get_project_cache_root(cls) -> str:
        """获取程序根目录下的 ProjectCache 根目录。"""
        return os.path.abspath(os.path.join(".", cls.CACHE_ROOT_NAME))

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

        cache_dir = cls.get_project_cache_dir(project.project_id)
        cache_path = os.path.join(cache_dir, cls.CACHE_FILENAME)
        stats_path = os.path.join(cache_dir, cls.STATS_FILENAME)
        cache_tmp_path = cache_path + f".{os.getpid()}.tmp"
        stats_tmp_path = stats_path + f".{os.getpid()}.tmp"

        with cls.CACHE_WRITE_LOCK:
            try:
                os.makedirs(cache_dir, exist_ok=True)

                # 先写临时文件，再 replace，避免读到半截文件
                content_bytes = msgspec.json.encode(project)
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
    def list_project_histories(cls, limit: int = 0, prune: bool = False) -> list[dict]:
        """扫描 ProjectCache 目录并返回历史项目列表。

        会按创建时间倒序排序；prune=True 时会清理无效目录和超出限制的旧项目。
        """
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
    def save_to_file(self) -> None:
        """保存当前项目缓存。"""
        if self.project is None:
            return

        with self.file_lock:
            self._ensure_project_metadata(self.project)
            self._write_project_cache_files(self.project)

    def save_to_file_tick(self) -> None:
        """定时保存任务。"""
        while not self.save_to_file_stop_flag:
            time.sleep(self.SAVE_INTERVAL)
            if getattr(self, "save_to_file_require_flag", False):
                self.save_to_file()
                self.save_to_file_require_flag = False

    def require_save_to_file(self, output_path: str | None = None) -> None:
        """请求保存缓存。output_path 参数仅保留兼容。"""
        self.save_to_file_require_flag = True

    def load_from_project(self, data: CacheProject):
        """直接从内存中的 CacheProject 对象加载项目。"""
        self._ensure_project_metadata(data)
        self.project = data

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
        """从缓存文件反序列化为 CacheProject。"""
        with open(cache_path, "rb") as reader:
            content_bytes = reader.read()

        try:
            # 优先按新 dataclass 结构解析
            return msgspec.json.decode(content_bytes, type=CacheProject)
        except msgspec.ValidationError:
            # 新结构失败后兼容旧结构和旧列表格式
            content = json.loads(content_bytes.decode("utf-8"))
            if isinstance(content, dict):
                return CacheProject.from_dict(content)
            return cls._read_from_old_content(content)

    @classmethod
    def _read_from_old_content(cls, content: list) -> CacheProject:
        """兼容旧版列表结构缓存。"""
        data_iter = iter(content)
        project_data = next(data_iter)
        init_data = {
            "project_id": project_data.get("project_id", ""),
            "project_type": project_data.get("project_type", ""),
            "project_name": project_data.get("project_name", ""),
            "project_create_time": project_data.get("project_create_time", ""),
            "input_path": project_data.get("input_path", ""),
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

    # 任务分片生成
    def generate_previous_chunks(
        self,
        all_items: list[CacheItem],
        previous_item_count: int,
        start_idx: int,
    ) -> List[CacheItem]:
        """根据当前片段起点生成上文片段。"""
        if not all_items or previous_item_count <= 0 or start_idx <= 0:
            return []

        from_idx = max(0, start_idx - previous_item_count)
        to_idx = min(start_idx, len(all_items))
        if from_idx >= to_idx:
            return []

        return all_items[from_idx:to_idx]

    def generate_item_chunks(
        self,
        limit_type: str,
        limit_count: int,
        previous_line_count: int,
        task_mode,
    ) -> Tuple[List[List[CacheItem]], List[List[CacheItem]], List[str]]:
        """按任务类型和限制条件生成待处理片段。"""
        chunks, previous_chunks, file_paths = [], [], []

        for file in self.project.files.values():
            # 先按任务模式筛选当前需要处理的条目
            if task_mode == TaskType.TRANSLATION:
                items = [item for item in file.items if item.translation_status == TranslationStatus.UNTRANSLATED]
            elif task_mode == TaskType.POLISH:
                items = [item for item in file.items if item.translation_status == TranslationStatus.TRANSLATED]
            else:
                items = []

            if not items:
                continue

            current_chunk, current_length = [], 0
            chunk_start_idx_in_filtered_list = 0

            for i, item in enumerate(items):
                item_length = item.get_token_count(item.source_text) if limit_type == "token" else 1

                # 新 chunk 开始时，记录它在筛选后列表中的起始索引
                if not current_chunk:
                    chunk_start_idx_in_filtered_list = i

                if current_chunk and (current_length + item_length > limit_count):
                    chunks.append(current_chunk)
                    previous_chunks.append(
                        self.generate_previous_chunks(items, previous_line_count, chunk_start_idx_in_filtered_list)
                    )
                    file_paths.append(file.storage_path)
                    current_chunk, current_length = [], 0
                    chunk_start_idx_in_filtered_list = i

                current_chunk.append(item)
                current_length += item_length

            if current_chunk:
                chunks.append(current_chunk)
                previous_chunks.append(
                    self.generate_previous_chunks(items, previous_line_count, chunk_start_idx_in_filtered_list)
                )
                file_paths.append(file.storage_path)

        return chunks, previous_chunks, file_paths

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
