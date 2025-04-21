import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class I18nextReader(BaseSourceReader):
    """
    读取 i18next JSON 文件 (支持嵌套结构)，
    并将原始路径信息存储在 CacheItem 的 'i18next_path' 属性中。
    """
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return "I18next"

    @property
    def support_file(self):
        return "json"

    @staticmethod
    def _is_i18next_like_structure(data: Any) -> bool:
        """递归检查数据结构是否类似 i18next JSON (字典或字符串叶子)。"""
        if isinstance(data, str):
            return True
        if isinstance(data, dict):
            if not data: return True
            return all(isinstance(k, str) and I18nextReader._is_i18next_like_structure(v)
                       for k, v in data.items())
        # i18next 不应包含列表、数字等作为非叶子节点的值
        # 特殊情况：有时复数形式会用数组，但这里简化，只允许 string/dict
        return False

    def can_read_by_content(self, file_path: Path) -> bool:
        """检查文件内容是否符合 i18next JSON 的典型结构。"""
        content_str = file_path.read_text(encoding="utf-8", errors='ignore')
        if not content_str.strip(): return False
        content = json.loads(content_str)
        if not isinstance(content, dict): return False
        return I18nextReader._is_i18next_like_structure(content)


    def _flatten_json(self, data: Dict[str, Any], current_path: List[str] = []) -> List[Tuple[List[str], str]]:
        """
        递归地将嵌套字典扁平化为 (路径列表, 值) 的元组列表。
        """
        items = []
        for k, v in data.items():
            new_path = current_path + [k] # 构建新的路径列表
            if isinstance(v, dict):
                items.extend(self._flatten_json(v, new_path))
            elif isinstance(v, str):
                # 到达叶子节点（字符串），存储路径列表和值
                items.append((new_path, v))
                pass
        return items

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        """
        读取 i18next JSON 文件，提取所有嵌套的键值对，并存储路径信息。
        """
        items = []

        content = file_path.read_text(encoding=detected_encoding or 'utf-8')
        json_data = json.loads(content)

        # 扁平化 JSON 获取 (路径列表, 值)
        flat_items_with_path = self._flatten_json(json_data)

        for path_list, value in flat_items_with_path:

            item = text_to_cache_item(value)

            item.i18next_path = path_list

            items.append(item)

        return items