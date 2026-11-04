"""活动项目的内存状态、并发访问与保存调度。"""
from collections import defaultdict
from typing import Callable, Dict, List, Tuple
import os
import posixpath
import re
import threading

from Backend.core.config import ConfigMixin
from Backend.domain.config.task_type import TaskType
from Backend.core.log import LogMixin
from Backend.core.protocol import to_wire
from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_item import CacheItem, TranslationStatus
from Backend.domain.models.cache_project import CacheProject, CacheProjectStatistics
from Backend.domain.models.intermediate import (
    generate_analysis_source_chunks, generate_item_chunks, generate_previous_chunks,
    normalize_project,
)
from Backend.infrastructure.files.accessors.cache_accessor import CacheAccessor
# Preserve the existing module-level migration helper import.
from Backend.infrastructure.files.accessors.cache_accessor import copy_legacy_extras


_ANY_PROJECT = object()


class CacheManager(CacheAccessor, ConfigMixin, LogMixin):
    """管理活动项目、并发访问与保存调度；文件访问由 CacheAccessor 提供。"""

    ANALYSIS_EXTRA_KEY = "analysis_v1"
    SAVE_INTERVAL = 8  # 缓存保存间隔（秒）

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

    def save_to_file_tick(self) -> None:
        """定时保存任务。"""
        while not self._save_stop_event.wait(self.SAVE_INTERVAL):
            if self._save_requested.is_set():
                try:
                    self.save_to_file()
                except Exception as error:
                    self.error(f"定时保存项目缓存失败，将在下一周期重试：{error}", error)

    def require_save_to_file(self) -> None:
        """请求在下一保存周期写入当前项目缓存。"""
        self._save_requested.set()

    def load_from_project(self, data: CacheProject):
        """直接从内存中的 CacheProject 对象加载项目。"""
        with self.file_lock:
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
        """按旧路径加载；未找到显式候选时，优先回退到最新项目历史。"""
        path = self.get_default_cache_path(output_path=output_path)
        default_path = os.path.join(self.get_project_cache_root(), self.CACHE_FILENAME)
        if path == default_path and self._find_existing_cache_path(output_path) is None:
            histories = self.list_project_histories(limit=1, prune=False)
            if histories:
                path = histories[0]["cache_path"]
        with self.file_lock:
            if os.path.isfile(path):
                self.project = self.read_from_file(path)
            else:
                self.project = None

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
                # Only normalize display paths; project.files retains its keys.
                directory, filename = posixpath.split(file_path.replace("\\", "/"))
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
            if cache_file:
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
                return
        # Log observers can synchronously query the cache; never call them under its lock.
        self.error(f"找不到缓存文件：{storage_path}")

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
            if cache_file:
                item_to_update = cache_file.get_item(text_index)
                item_to_update.translated_text = new_text
                if not new_text or not new_text.strip():
                    item_to_update.translation_status = TranslationStatus.UNTRANSLATED
                else:
                    item_to_update.translation_status = translation_status
                return
        self.error(f"找不到缓存文件：{storage_path}")

    def _query_project_locked(self, expected_project_id):
        project = self.project
        current_id = project.project_id if project else None
        if expected_project_id is not _ANY_PROJECT and expected_project_id != current_id:
            raise PipelineError("PROJECT_CHANGED", "项目已切换，请刷新后重试", 409)
        return project

    def search_items(self, query: str, scope: str, is_regex: bool, search_flagged: bool,
                     *, expected_project_id=_ANY_PROJECT) -> list:
        """Search only the project whose identity was checked under the lock."""
        return self._search_items(
            query, scope, is_regex, search_flagged, expected_project_id=expected_project_id,
        )

    def search_items_snapshot(self, query: str, scope: str, is_regex: bool, search_flagged: bool,
                              *, expected_project_id=_ANY_PROJECT) -> dict:
        """Return matching rows and their project as one consistent response."""
        return self._search_items(
            query, scope, is_regex, search_flagged,
            expected_project_id=expected_project_id, include_project=True,
        )

    def _search_items(self, query, scope, is_regex, search_flagged,
                      *, expected_project_id, include_project=False):
        error_message = None
        with self.file_lock:
            project = self._query_project_locked(expected_project_id)
            try:
                result = self._search_items_locked(project, query, scope, is_regex, search_flagged)
            except re.error as error:
                error_message = f"无效的正则表达式: {error}"
                result = []
            if include_project:
                result = {"result": to_wire(result), "project": to_wire(project) if project else None}
        if error_message is not None:
            self.error(error_message)
        return result

    def _search_items_locked(self, project, query, scope, is_regex, search_flagged):
        results = []
        if project is None:
            return results
        fields_to_check = ["source_text", "translated_text"] if scope == "all" else [scope]

        if is_regex:
            # 预编译正则表达式以提高效率；错误交给外层解锁后记录。
            regex = re.compile(query)
            matcher = lambda text: regex.search(text)
        else:
            matcher = lambda text: query in text

        for file_path, cache_file in project.files.items():
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
        return generate_analysis_source_chunks(self.project, limit_type, limit_count)

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
