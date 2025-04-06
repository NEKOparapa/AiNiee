import shutil
from pathlib import Path

from bs4 import BeautifulSoup

from ModuleFolders.FileAccessor import ZipUtil


class DocxAccessor:
    def __init__(self, temp_folder="DocxCache"):
        self.temp_folder = temp_folder

    def temp_path_of(self, file_path: Path):
        return file_path.parent / self.temp_folder

    def read_content(self, source_file_path: Path, temp_root: Path = None):
        extract_path = temp_root if temp_root else self.temp_path_of(source_file_path)
        ZipUtil.decompress_zip_to_path(source_file_path, extract_path)
        the_file_path = extract_path / 'word' / 'document.xml'

        # 读取xml内容
        xml_soup = BeautifulSoup(the_file_path.read_text(encoding='utf-8'), 'xml')
        return xml_soup

    def write_content(
        self, content: BeautifulSoup, write_file_path: Path,
        source_file_path: Path, temp_root: Path = None,
    ):
        extract_path = temp_root if temp_root else self.temp_path_of(source_file_path)
        # 找不到文档文件就解压原文件
        the_file_path = extract_path / 'word' / 'document.xml'
        if not the_file_path.exists():
            ZipUtil.decompress_zip_to_path(source_file_path, extract_path)

        # 写入soup
        the_file_path.write_text(str(content), encoding='utf-8')
        ZipUtil.compress_to_zip_file(extract_path, write_file_path)

    def clear_temp(self, file_path: Path, temp_root: Path = None):
        extract_path = temp_root if temp_root else self.temp_path_of(file_path)
        if extract_path.exists():
            shutil.rmtree(extract_path)
