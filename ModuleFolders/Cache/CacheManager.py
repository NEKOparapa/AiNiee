import os
import threading
import time
from dataclasses import fields
from typing import List, Tuple

import rapidjson as json

from Base.Base import Base
from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import (
    CacheProject,
    CacheProjectStatistics
)


class CacheManager(Base):
    SAVE_INTERVAL = 8  # 缓存保存间隔（秒）

    def __init__(self) -> None:
        super().__init__()

        # 默认值
        self.project = CacheProject()

        # 线程锁
        self.file_lock = threading.Lock()

        # 注册事件
        self.subscribe(Base.EVENT.TRANSLATION_START, self.start_interval_saving)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)

    def start_interval_saving(self, event: int, data: dict):
        # 定时器
        self.save_to_file_stop_flag = False
        threading.Thread(target=self.save_to_file_tick, daemon=True).start()

    # 应用关闭事件
    def app_shut_down(self, event: int, data: dict) -> None:
        self.save_to_file_stop_flag = True

    # 保存缓存到文件
    def save_to_file(self) -> None:
        """保存缓存到文件，缓存结构：
        {
            "project_id": "aaa",
            "project_type": "Type",
            "files": {
                "path/to/file1.txt": {
                    "storage_path": "...",
                    "file_name": "...",
                    "items": {
                        1: {"text_index": 1, "source_text": "...", ...},
                        2: {"text_index": 2, "source_text": "...", ...},
                    }
                },
                "path/to/file2.txt": { ... }
            }
        }
        """
        path = os.path.join(self.save_to_file_require_path, "cache", "AinieeCacheData.json")
        with self.file_lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as writer:
                writer.write(json.dumps(self.project.to_dict(), ensure_ascii=False))

    # 保存缓存到文件的定时任务
    def save_to_file_tick(self) -> None:
        """定时保存任务"""
        while not self.save_to_file_stop_flag:
            time.sleep(self.SAVE_INTERVAL)
            if getattr(self, "save_to_file_require_flag", False):
                self.save_to_file()
                self.emit(Base.EVENT.CACHE_FILE_AUTO_SAVE, {})
                self.save_to_file_require_flag = False

    # 请求保存缓存到文件
    def require_save_to_file(self, output_path: str) -> None:
        """请求保存缓存"""
        self.save_to_file_require_path = output_path
        self.save_to_file_require_flag = True

    # 从项目中加载
    def load_from_project(self, data: CacheProject):
        self.project = data

    # 从缓存文件读取数据
    def load_from_file(self, output_path: str) -> None:
        """从文件加载数据"""
        path = os.path.join(output_path, "cache", "AinieeCacheData.json")
        with self.file_lock:
            if os.path.isfile(path):
                self.project = self.read_from_file(path)

    @classmethod
    def read_from_file(cls, cache_path) -> CacheProject:
        with open(cache_path, "r", encoding="utf-8") as reader:
            content = json.load(reader)
        if isinstance(content, list):
            # 旧版缓存
            return cls._read_from_old_content(content)
        else:
            # 新版缓存
            return CacheProject.from_dict(content)

    @classmethod
    def _read_from_old_content(cls, content: list) -> CacheProject:
        # 兼容旧版缓存
        data_iter = iter(content)
        project_data = next(data_iter)
        init_data = {
            "project_id": project_data["project_id"],
            "project_type": project_data["project_type"],
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
        # 这两个属性之前是放item，现在放file
        file_extra_keys = set(["subtitle_title", "top_text"])
        file_prop_keys = set(["file_project_type"])
        for old_item in data_iter:
            storage_path = old_item["storage_path"]
            if storage_path not in files_props:
                files_props[storage_path] = {"items": [], "extra": {}}
            new_item = CacheItem.from_dict(old_item)
            for k, v in old_item.items():
                if k == 'file_name':
                    continue
                if k not in new_item_fields:
                    if k in file_prop_keys:
                        files_props[storage_path][k] = v
                    elif k in file_extra_keys:
                        files_props[storage_path]["extra"][k] = v
                    else:
                        new_item.set_extra(k, v)
            files_props[storage_path]["items"].append(new_item)

        init_data["files"] = {
            k: CacheFile(**v)
            for k, v in files_props.items()
        }
        return CacheProject(**init_data)

    # 获取缓存内全部文本对数量
    def get_item_count(self) -> int:
        """获取总缓存项数量"""
        return self.project.count_items()

    # 获取某翻译状态的条目数量
    def get_item_count_by_status(self, status: int) -> int:
        return self.project.count_items(status)

    # 检测是否存在需要翻译的条目
    def get_continue_status(self) -> bool:
        """检查是否存在可继续翻译的状态"""
        has_translated = False
        has_untranslated = False
        for item in self.project.items_iter():
            status = item.translation_status
            if status == CacheItem.STATUS.TRANSLATED:
                has_translated = True
            elif status == CacheItem.STATUS.UNTRANSLATED:
                has_untranslated = True
            if has_translated and has_untranslated:
                return True
        return has_translated and has_untranslated

    # 生成上文数据条目片段
    def generate_previous_chunks(self, items: list[CacheItem], previous_line_count: int, start_idx: int) -> List[CacheItem]:
        """生成上文片段"""
        if not items:
            return []
        collected = []
        i = start_idx - 1
        while i >= 0 and len(collected) < previous_line_count:
            if items[i].text_index == start_idx - len(collected) - 1:
                collected.append(items[i])
                i -= 1
            else:
                break
        return list(reversed(collected))

    # 生成待翻译片段
    def generate_item_chunks(self, limit_type: str, limit_count: int, previous_line_count: int) -> Tuple[List[List[CacheItem]], List[List[CacheItem]]]:
        chunks, previous_chunks = [], []
        for file in self.project.files.values():
            items = [item for item in file.items if item.translation_status == CacheItem.STATUS.UNTRANSLATED]
            if not items:
                continue
            current_chunk, current_length = [], 0
            for item in items:
                item_length = item.token_count if limit_type == "token" else 1
                if current_chunk and (current_length + item_length > limit_count):
                    chunks.append(current_chunk)
                    previous_chunks.append(
                        self.generate_previous_chunks(items, previous_line_count, file.index_of(current_chunk[0].text_index))
                    )
                    current_chunk, current_length = [], 0
                current_chunk.append(item)
                current_length += item_length
            if current_chunk:
                chunks.append(current_chunk)
                previous_chunks.append(
                    self.generate_previous_chunks(items, previous_line_count, file.index_of(current_chunk[0].text_index))
                )
        return chunks, previous_chunks
