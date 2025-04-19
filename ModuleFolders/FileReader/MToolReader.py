import json
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class MToolReader(BaseSourceReader):
    """读取Mtool json文件"""
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return "Mtool"

    @property
    def support_file(self):
        return "json"

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        items = []
        json_data = json.loads(file_path.read_text(encoding='utf-8'))

        # 提取键值对
        for key, value in json_data.items():
            # 根据 JSON 文件内容的数据结构，获取相应字段值
            item = text_to_cache_item(key, value)
            items.append(item)
        return items

    def can_read_by_content(self, file_path: Path) -> bool:
        # {"source_text1": "source_text1?", "source_text2": "source_text2?"}
        # 即使不是对应编码也不影key value的形式
        content = json.loads(file_path.read_text(encoding="utf-8", errors='ignore'))
        if not isinstance(content, dict):
            return False
        return all(isinstance(k, str) and isinstance(v, str) for k, v in content.items())
