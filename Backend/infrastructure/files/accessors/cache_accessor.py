"""项目缓存文件、统计、历史与旧格式迁移，不持有活动项目或保存线程。"""
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar
import copy
import os
import shutil
import threading
import uuid

import msgspec
import rapidjson as json

from Backend.core.paths import project_cache_root
from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_item import CacheItem
from Backend.domain.models.cache_project import CacheProject, CacheProjectStatistics
from Backend.domain.models.intermediate import SCHEMA_VERSION, normalize_project, parse_model


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


class CacheAccessor:
    """无实例状态的缓存访问接口，可独立使用或由内存缓存管理器继承。"""

    CACHE_FILENAME = "AinieeCacheData.json"
    STATS_FILENAME = "ProjectStatistics.json"
    HISTORY_LIMIT = 3
    CACHE_WRITE_LOCK: ClassVar[threading.Lock] = threading.Lock()

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
        """推导缓存路径，仅检查旧路径候选的存在性，不扫描项目历史。

        优先走新的 ProjectCache/<project_id>/AinieeCacheData.json；
        output_path 仅保留给旧调用方和旧缓存兼容读取使用。
        """
        if project_id:
            return os.path.join(cls.get_project_cache_dir(project_id), cls.CACHE_FILENAME)

        return cls._find_existing_cache_path(output_path) or os.path.join(
            cls.get_project_cache_root(), cls.CACHE_FILENAME,
        )

    @classmethod
    def _find_existing_cache_path(cls, output_path: str) -> str | None:
        """按旧接口优先级检查显式文件及两种目录布局。"""
        if output_path:
            if os.path.isfile(output_path):
                return output_path

            direct_cache_path = os.path.join(output_path, cls.CACHE_FILENAME)
            if os.path.isfile(direct_cache_path):
                return direct_cache_path

            legacy_cache_path = os.path.join(output_path, "cache", cls.CACHE_FILENAME)
            if os.path.isfile(legacy_cache_path):
                return legacy_cache_path

        return None

    @classmethod
    def get_project_statistics_path(cls, project_id: str) -> str:
        """获取项目统计文件路径。"""
        return os.path.join(cls.get_project_cache_dir(project_id), cls.STATS_FILENAME)

    @classmethod
    def read_project_statistics(cls, project_id: str) -> dict | None:
        """Read ProjectStatistics.json for the given project."""
        if not project_id:
            return None
        return cls._read_statistics_payload(cls.get_project_statistics_path(project_id))

    @classmethod
    def _get_now_iso(cls) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @classmethod
    def _timestamp_to_iso(cls, timestamp) -> str:
        if timestamp is None:
            return cls._get_now_iso()
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")

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
    ) -> tuple[int, int]:
        """只读推导项目进度，不修改项目或统计数据。

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
        return total_line, line

    @classmethod
    def _build_stats_payload(
        cls,
        project: CacheProject,
        stats_payload: dict | None = None,
    ) -> dict:
        """构建写入 ProjectStatistics.json 的内容。"""
        total_line, line = cls._normalize_progress(project, stats_payload)
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
        with cls.CACHE_WRITE_LOCK:
            # Identity and paths must stay consistent even for standalone accessor callers.
            cls._ensure_project_metadata(project)
            normalize_project(project)

            cache_dir = cls.get_project_cache_dir(project.project_id)
            cache_path = os.path.join(cache_dir, cls.CACHE_FILENAME)
            stats_path = os.path.join(cache_dir, cls.STATS_FILENAME)
            cache_tmp_path = cache_path + f".{os.getpid()}.tmp"
            stats_tmp_path = stats_path + f".{os.getpid()}.tmp"

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

            try:
                history = cls._build_history_entry_from_stats(
                    entry.path,
                    cache_path,
                    stats_path,
                    stats_payload,
                )
            except FileNotFoundError:
                # A concurrent deletion may remove an old entry before its ctime fallback.
                continue
            histories.append(history)

        if prune:
            for project_id in invalid_project_ids:
                cls.delete_project_cache(project_id)

        # 按项目创建时间倒序排列，最新项目排在最前
        histories.sort(
            key=cls._history_sort_key,
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

    @staticmethod
    def _history_sort_key(history: dict) -> tuple[float, str]:
        """按实际时间排序；旧无时区记录沿用生成时的本机本地时间语义。"""
        try:
            created = datetime.fromisoformat(history.get("project_create_time", ""))
            timestamp = created.timestamp()
        except (TypeError, ValueError, OverflowError, OSError):
            timestamp = float("-inf")
        return timestamp, history.get("project_id", "")

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
