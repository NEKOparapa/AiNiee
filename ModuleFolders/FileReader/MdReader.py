from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)
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
        return ProjectType.MD

    @property
    def support_file(self):
        return "md"

    def read_source_file(self, file_path: Path) -> CacheFile:
        cache_file = self.txt_reader.read_source_file(file_path)
        for item in cache_file.items:
            item.set_extra("original_line", item.source_text)
        return cache_file

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        # 重载抽象方法，实际不需要使用
        raise NotImplementedError
