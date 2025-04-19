import json
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class VntReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return "Vnt"

    @property
    def support_file(self):
        return "json"

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        json_data = json.loads(file_path.read_text(encoding="utf-8"))
        items = []
        for entry in json_data:
            source_text = entry["message"]
            item = text_to_cache_item(source_text)
            names = entry.get("names", [])  # 默认获取空列表
            name = entry.get("name", "")    # 默认获取空字符串

            if names:
                # 处理names列表，拼接每个名字
                name_tags = ''.join([f'[{n}]' for n in names])
                new_source_text = f"{name_tags}{source_text}"
                item.set_source_text(new_source_text)
                item.names = names
            elif name:
                # 处理单个name字段
                new_source_text = self.combine_srt(name, source_text)
                item.set_source_text(new_source_text)
                item.name = name
            # 无name或names字段时不处理

            items.append(item)
        return items

    def combine_srt(self, name, text):
        return f"[{name}]{text}"

    def can_read_by_content(self, file_path: Path) -> bool:
        # [{"mesage": "text1"}, {"message": "text2"}]
        # 即使不是对应编码也不影响英文的key
        content = json.loads(file_path.read_text(encoding="utf-8", errors='ignore'))
        if not isinstance(content, list):
            return False
        return all(isinstance(line, dict) and 'message' in line for line in content)
