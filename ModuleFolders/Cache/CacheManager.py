from collections import defaultdict
import os
import re
import threading
import time
from dataclasses import fields
from typing import Dict, List, Tuple

import msgspec
import rapidjson as json

from Base.Base import Base
from ModuleFolders.TaskConfig.TaskType import TaskType
from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem, TranslationStatus
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
        self.subscribe(Base.EVENT.TASK_START, self.start_interval_saving)
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
            content_bytes = msgspec.json.encode(self.project)
            with open(path, "wb") as writer:
                writer.write(content_bytes)

            # 写入项目整体翻译状态文件
            total_line = self.project.stats_data.total_line # 获取需翻译总行数
            line = self.project.stats_data.line # 获取已翻译行数
            json_data = {"total_line": total_line, "line": line }

            json_path = os.path.join(self.save_to_file_require_path, "cache", "ProjectStatistics.json")
            with open(json_path, "w", encoding="utf-8") as writer:
                json.dump(json_data, writer, ensure_ascii=False, indent=4)  # 直接写入 JSON 数据

    # 保存缓存到文件的定时任务
    def save_to_file_tick(self) -> None:
        """定时保存任务"""
        while not self.save_to_file_stop_flag:
            time.sleep(self.SAVE_INTERVAL)
            if getattr(self, "save_to_file_require_flag", False):
                self.save_to_file()
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
        with open(cache_path, "rb") as reader:
            content_bytes = reader.read()
        try:
            # 反序列化严格按照dataclass定义，如source_text这种非optional类型不能为None，否则反序列化失败
            return msgspec.json.decode(content_bytes, type=CacheProject)
        except msgspec.ValidationError:
            content = json.loads(content_bytes.decode('utf-8'))
            if isinstance(content, dict):
                return CacheProject.from_dict(content)
            else:
                return cls._read_from_old_content(content)

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
                files_props[storage_path] = {
                    "items": [],
                    "extra": {},
                    "file_project_type": project_data["project_type"],
                    'storage_path': storage_path,
                }
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
            if status == TranslationStatus.TRANSLATED:
                has_translated = True
            elif status == TranslationStatus.UNTRANSLATED:
                has_untranslated = True
            if has_translated and has_untranslated:
                return True
        return has_translated and has_untranslated

    # 生成上文数据条目片段
    def generate_previous_chunks(self, all_items: list[CacheItem], previous_item_count: int, start_idx: int) -> List[CacheItem]:

        # 如果没有条目，或者上文条目数小于等于0，或者起始索引小于等于0，则返回空列表
        if not all_items or previous_item_count <= 0 or start_idx <= 0:
            return []

        # 计算实际要获取的上文的起始索引 (包含)
        from_idx = max(0, start_idx - previous_item_count)

        # 计算实际要获取的上文的结束索引 (不包含)
        to_idx = min(start_idx, len(all_items)) # 通常就是 start_idx

        # 如果计算出的范围无效，返回空列表
        if from_idx >= to_idx:
            return []

        # 直接切片获取所需范围的条目，切片会自动处理边界情况，例如 from_idx=0
        collected = all_items[from_idx:to_idx]

        return collected

    # 生成待翻译片段
    def generate_item_chunks(self, limit_type: str, limit_count: int, previous_line_count: int, task_mode) -> \
            Tuple[List[List[CacheItem]], List[List[CacheItem]], List[str]]:
        chunks, previous_chunks, file_paths = [], [], []  # 添加 file_paths 初始化

        # 遍历所有文件
        for file in self.project.files.values():

            # 根据任务模式筛选条目
            if task_mode == TaskType.TRANSLATION : # 选取未翻译条目
                items = [item for item in file.items if item.translation_status == TranslationStatus.UNTRANSLATED]
            elif task_mode == TaskType.POLISH: # 选取已翻译条目
                items = [item for item in file.items if item.translation_status == TranslationStatus.TRANSLATED]

            # 如果没有需要翻译的条目，则跳过
            if not items:
                continue

            current_chunk, current_length = [], 0

            # 遍历该文件的所有条目
            for item in items:
                # 计算当前条目的长度
                item_length = item.get_token_count(item.source_text) if limit_type == "token" else 1

                # 如果当前片段长度加上当前条目长度超过限制，则将当前片段添加到结果列表中，并重置当前片段
                if current_chunk and (current_length + item_length > limit_count):
                    # 添加到原文片段列表
                    chunks.append(current_chunk)

                    # 生成上文数据片段
                    previous_chunks.append(
                        self.generate_previous_chunks(items, previous_line_count, file.index_of(current_chunk[0].text_index))
                    )

                    # 添加chunk对应的文件路径
                    file_paths.append(file.storage_path)  # 添加文件路径记录

                    # 重置片段暂存容器
                    current_chunk, current_length = [], 0

                # 添加当前条目
                current_chunk.append(item)
                current_length += item_length

            # 处理最后一个未添加到 chunks 的片段
            if current_chunk:
                # 添加到原文片段列表
                chunks.append(current_chunk)

                # 生成上文数据片段
                previous_chunks.append(
                    self.generate_previous_chunks(items, previous_line_count, file.index_of(current_chunk[0].text_index))
                )

                # 添加chunk对应的文件路径
                file_paths.append(file.storage_path)  # 添加文件路径记录

        # 返回结果列表
        return chunks, previous_chunks, file_paths 


    # 获取文件层级结构
    def get_file_hierarchy(self) -> Dict[str, List[str]]:
        """
        从缓存中读取文件列表，并按文件夹层级组织。
        """
        hierarchy = defaultdict(list)
        if not self.project or not self.project.files:
            return {}
            
        with self.file_lock:
            for file_path in self.project.files.keys():
                # os.path.split 将路径分割成 (目录, 文件名)
                directory, filename = os.path.split(file_path)
                # 如果文件在根目录，directory会是空字符串，用'.'代替
                if not directory:
                    directory = '.'
                hierarchy[directory].append(filename)

        # 对每个文件夹下的文件名进行排序
        for dir_path in hierarchy:
            hierarchy[dir_path].sort()
            
        return dict(hierarchy)

    # 更新缓存中的特定文本项
    def update_item_text(self, storage_path: str, text_index: int, field_name: str, new_text: str) -> None:
        """
        更新缓存中指定文件、指定索引的文本项的某个字段。
        """
        with self.file_lock:
            cache_file = self.project.get_file(storage_path)
            if not cache_file:
                print(f"Error: 找不到文件 {storage_path}")
                return
            
            item_to_update = cache_file.get_item(text_index)
            
            # 修改原文
            if field_name == 'source_text':
                if new_text and new_text.strip():
                    if item_to_update.source_text != new_text:
                        item_to_update.source_text = new_text

            # 修改译文
            elif field_name == 'translated_text':
                item_to_update.translated_text = new_text
                # 如果原文和译文不同，则标记为已翻译
                if new_text and new_text.strip():
                    if item_to_update.source_text != new_text:
                            item_to_update.translation_status = TranslationStatus.TRANSLATED

            # 修改润文
            elif field_name == 'polished_text':
                item_to_update.polished_text = new_text
                # 只要有润文，就标记为已润色
                if new_text and new_text.strip():
                    item_to_update.translation_status = TranslationStatus.POLISHED
            else:
                print(f"Error: 不支持更新字段 {field_name}")
                return

    # 缓存重编排方法
    def reformat_and_splice_cache(self, file_path: str, formatted_data: dict, selected_item_indices: list[int]) -> list[CacheItem] | None:
        """
        根据格式化后的数据，对指定文件中的选中项进行“切片和拼接”操作。
        此操作会移除旧的选中项，并在原位置插入新的项。

        Args:
            file_path (str): 要更新的文件路径。
            formatted_data (dict): 从API返回的格式化数据。
                                   格式: {'0': {'text': '...', 'blank_lines_after': ...}, ...}
            selected_item_indices (list[int]): 原始被选中项的 text_index 列表。

        Returns:
            list[CacheItem] | None: 成功则返回代表整个文件的、更新后的完整CacheItem列表，否则返回None。
        """
        with self.file_lock:
            cache_file = self.project.get_file(file_path)
            if not cache_file:
                self.error(f"在缓存中找不到文件: {file_path}")
                return None
            
            original_items = cache_file.items
            if not selected_item_indices or not original_items:
                return original_items # 如果没有选中项或文件为空，则不进行任何操作

            # 创建新的CacheItem
            newly_created_items = []
            language_stats = cache_file.language_stats
            
            # 为了保证text_index的全局唯一性，从当前所有item的最大index开始递增
            max_text_index = 0
            for item in self.project.items_iter():
                if item.text_index > max_text_index:
                    max_text_index = item.text_index

            sorted_formatted_data = sorted(formatted_data.items(), key=lambda x: int(x[0]))
            
            for _, item_data in sorted_formatted_data:
                max_text_index += 1
                new_item = CacheItem(
                    text_index=max_text_index,
                    source_text=item_data.get('text', ''),
                    translation_status=TranslationStatus.UNTRANSLATED,
                    lang_code=language_stats[0] if language_stats else None,
                )
                new_item.set_extra('line_break', item_data.get('blank_lines_after', 0))
                newly_created_items.append(new_item)

            # 找到插入点和要替换的范围
            selected_indices_set = set(selected_item_indices)
            
            # 找到选中范围在原列表中的起始和结束index
            start_pos = next(i for i, item in enumerate(original_items) if item.text_index in selected_indices_set)
            end_pos = next(i for i, item in reversed(list(enumerate(original_items))) if item.text_index in selected_indices_set)

            # 构建最终的 item 列表
            final_items = (
                original_items[:start_pos] + 
                newly_created_items + 
                original_items[end_pos + 1:]
            )

            # 更新缓存
            cache_file.items = final_items
            if hasattr(cache_file, "items_index_dict"):
                del cache_file.items_index_dict # 清除旧缓存，以便重新计算

            return final_items

    # 缓存全搜索方法
    def search_items(self, query: str, scope: str, is_regex: bool) -> list:
        """
        在整个项目中搜索条目。

        Args:
            query (str): 搜索查询字符串。
            scope (str): 搜索范围 ('all', 'source_text', 'translated_text', 'polished_text')。
            is_regex (bool): 是否使用正则表达式。

        Returns:
            list: 包含元组 (file_path, original_row_num, CacheItem) 的结果列表。
        """
        results = []
        fields_to_check = []

        if scope == 'all':
            fields_to_check = ['source_text', 'translated_text', 'polished_text']
        else:
            fields_to_check = [scope]

        try:
            if is_regex:
                # 预编译正则表达式以提高效率
                regex = re.compile(query)
                matcher = lambda text: regex.search(text)
            else:
                matcher = lambda text: query in text
        except re.error as e:
            # 正则表达式无效，可以发出一个错误信号或直接返回空
            self.error(f"无效的正则表达式: {e}")
            # 这里可以向UI发送一个错误提示
            return []

        with self.file_lock:
            for file_path, cache_file in self.project.files.items():
                for item_index, item in enumerate(cache_file.items):
                    found = False
                    for field_name in fields_to_check:
                        text_to_check = getattr(item, field_name, None)
                        if text_to_check and matcher(text_to_check):
                            # (文件路径, 原始行号, 完整的CacheItem对象)
                            results.append((file_path, item_index + 1, item))
                            found = True
                            break  # 找到一个匹配就跳出字段循环，避免重复添加
                    if found:
                        continue
        return results