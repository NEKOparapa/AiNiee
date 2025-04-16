from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import BaseSourceReader, InputConfig
from ModuleFolders.FileReader.TxtReader import TxtReader


class MdReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)
        self.txt_reader = TxtReader(input_config, None)  # 简单复用TxtReader，如有另外实现请删除

    def __enter__(self):
        self.txt_reader.__enter__()
        return super().__enter__()

    def __exit__(self, exc_type, exc, exc_tb):
        self.txt_reader.__exit__(exc_type, exc, exc_tb)
        return super().__exit__(exc_type, exc, exc_tb)

    @classmethod
    def get_project_type(cls):
        return "Md"

    @property
    def support_file(self):
        return "md"

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        items = self.txt_reader.read_source_file(file_path, detected_encoding)
        for item in items:
            item.original_line = item.get_source_text()
        return items
