from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
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
        self, translation_file_path: Path, cache_file: CacheFile,
        source_file_path: Path = None,
    ):
        self.txt_writer.write_translated_file(translation_file_path, cache_file, source_file_path)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        # 重载抽象方法，实际不需要使用
        raise NotImplementedError

    @classmethod
    def get_project_type(self):
        return ProjectType.MD
