from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileAccessor.DocxAccessor import DocxAccessor
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)


class DocxWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)
        self.file_accessor = DocxAccessor()

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        temp_root = self.file_accessor.temp_path_of(source_file_path)
        content = self.file_accessor.read_content(source_file_path, temp_root)
        start_index = 0
        # 根据 w:t 标签找到原文
        paragraphs = content.find_all("w:t")
        for match in paragraphs:
            if isinstance(match.string, str) and match.string.strip():
                # 在翻译结果中查找是否存在原文，存在则替换并右移开始下标
                for content_index in range(start_index, len(items)):
                    if match.string == items[content_index].get_source_text():
                        match.string = items[content_index].get_translated_text()
                        start_index = content_index + 1
                        break
        self.file_accessor.write_content(
            content, translation_file_path, source_file_path, temp_root
        )
        self.file_accessor.clear_temp(source_file_path, temp_root)

    @classmethod
    def get_project_type(self):
        return "Docx"
