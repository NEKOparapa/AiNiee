from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileAccessor.DocxAccessor import DocxAccessor
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class DocxReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)
        self.file_accessor = DocxAccessor()

    @classmethod
    def get_project_type(cls):
        return 'Docx'

    @property
    def support_file(self):
        return 'docx'

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        xml_soup = self.file_accessor.read_content(file_path)
        paragraphs = xml_soup.find_all('w:t')
        self.file_accessor.clear_temp(file_path)
        # 过滤掉空的内容
        filtered_matches = (match.string for match in paragraphs if isinstance(match.string, str) and match.string.strip())
        items = [
            text_to_cache_item(text) for text in filtered_matches
            if not (text == "" or text == "\n" or text == " " or text == '\xa0')
        ]
        return items
