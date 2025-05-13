from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileAccessor.DocxAccessor import DocxAccessor
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class DocxReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)
        self.file_accessor = DocxAccessor()

    @classmethod
    def get_project_type(cls):
        return ProjectType.DOCX

    @property
    def support_file(self):
        return 'docx'

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        xml_soup = self.file_accessor.read_content(file_path)
        paragraphs = xml_soup.find_all('w:t')
        # 过滤掉空的内容
        filtered_matches = (match.string for match in paragraphs if isinstance(match.string, str) and match.string.strip())
        items = [
            CacheItem(source_text=str(text)) for text in filtered_matches
            if not (text == "" or text == "\n" or text == " " or text == '\xa0')
        ]
        return CacheFile(items=items)
