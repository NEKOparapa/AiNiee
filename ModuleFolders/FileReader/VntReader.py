import json
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class VntReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.VNT

    @property
    def support_file(self):
        return "json"

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        json_data = json.loads(file_path.read_text(encoding="utf-8"))
        items = []
        for entry in json_data:
            source_text = entry["message"]
            names = entry.get("names", [])  # 默认获取空列表
            name = entry.get("name", "")    # 默认获取空字符串

            extra = {}
            if names:
                # 处理names列表，拼接每个名字
                name_tags = ''.join([f'[{n}]' for n in names])
                source_text = f"{name_tags}{source_text}"
                extra["names"] = names
            elif name:
                # 处理单个name字段
                source_text = self.combine_srt(name, source_text)
                extra["name"] = name
            # 无name或names字段时不处理
            item = CacheItem(source_text=source_text, extra=extra)
            items.append(item)
        return CacheFile(items=items)

    def combine_srt(self, name, text):
        return f"[{name}]{text}"

    def can_read_by_content(self, file_path: Path) -> bool:
        # [{"mesage": "text1"}, {"message": "text2"}]
        # 即使不是对应编码也不影响英文的key
        content = json.loads(file_path.read_text(encoding="utf-8", errors='ignore'))
        if not isinstance(content, list):
            return False
        return all(isinstance(line, dict) and 'message' in line for line in content)
