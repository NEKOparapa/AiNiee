import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

from ModuleFolders.FileAccessor import ZipUtil


class DocxAccessor:

    def read_content(self, source_file_path: Path):
        with zipfile.ZipFile(source_file_path) as zipf:
            content = zipf.read("word/document.xml").decode("utf-8")
        # 读取xml内容
        xml_soup = BeautifulSoup(content, 'xml')
        return xml_soup

    def write_content(
        self, content: BeautifulSoup, write_file_path: Path,
        source_file_path: Path,
    ):
        ZipUtil.replace_in_zip_file(
            source_file_path, write_file_path, {"word/document.xml": str(content)}
        )
