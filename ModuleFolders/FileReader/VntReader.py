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

    def read_source_file(self, file_path: Path) -> list[CacheItem]:
        json_data = json.loads(file_path.read_text(encoding="utf-8"))
        items = []
        for entry in json_data:
            source_text = entry["message"]
            item = text_to_cache_item(source_text)
            name = entry.get("name")
            if name:
                # 直接拼接【人名】+文本
                new_source_text = self.combine_srt(name, source_text)
                item.set_source_text(new_source_text)
                item.name = name
            items.append(item)
        return items

    def combine_srt(self, name, text):
        return f"[{name}]{text}"
