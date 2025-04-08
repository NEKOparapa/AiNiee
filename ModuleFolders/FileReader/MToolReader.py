import json
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
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

    def read_source_file(self, file_path: Path, cache_project: CacheProject) -> list[CacheItem]:
        items = []
        json_data = json.loads(file_path.read_text(encoding='utf-8'))

        # 提取键值对
        for key, value in json_data.items():
            # 根据 JSON 文件内容的数据结构，获取相应字段值
            item = text_to_cache_item(key, value)
            items.append(item)
        return items
