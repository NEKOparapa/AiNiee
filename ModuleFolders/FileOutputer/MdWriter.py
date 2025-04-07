from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)
from ModuleFolders.FileOutputer.TxtWriter import TxtWriter


class MdWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)
        self.txt_writer = TxtWriter(output_config)  # 简单复用TxtWriter，如有另外实现请删除

    def __enter__(self):
        self.txt_writer.__enter__()
        return super().__enter__()

    def __exit__(self, exc_type, exc, exc_tb):
        self.txt_writer.__exit__(exc_type, exc, exc_tb)
        return super().__exit__(exc_type, exc, exc_tb)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        self.txt_writer.write_translated_file(translation_file_path, items, source_file_path)

    @classmethod
    def get_project_type(self):
        return "Md"
