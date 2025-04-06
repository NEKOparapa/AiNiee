import shutil
from pathlib import Path

import ebooklib
from ebooklib import epub

from ModuleFolders.FileAccessor import ZipUtil


class EpubAccessor:
    def __init__(self, temp_folder="EpubCache"):
        self.temp_folder = temp_folder

    def temp_path_of(self, file_path: Path):
        return file_path.parent / self.temp_folder

    def read_content(self, source_file_path: Path, temp_root: Path = None):
        extract_path = temp_root if temp_root else self.temp_path_of(source_file_path)
        ZipUtil.decompress_zip_to_path(source_file_path, extract_path)

        # 由于ebook给的相对路径与epub解压后路径是不准 遍历文件夹中的所有文件,找到文件
        book_file_dict = self._get_book_file_dict(extract_path)
        book = epub.read_epub(source_file_path)  # 加载EPUB文件
        result: dict[str, str] = {}
        for item in book.get_items():
            # 检查是否是文本内容
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # 获取文件的唯一ID及文件名
                item_id = item.get_id()
                file_name = Path(item.get_name()).name
                if file_name in book_file_dict:
                    html_content = book_file_dict[file_name].read_text(encoding='utf-8')
                    result[item_id] = html_content
        return result

    def write_content(
        self, content: dict[str, str], write_file_path: Path,
        source_file_path: Path, temp_root: Path = None,
    ):
        extract_path = temp_root if temp_root else self.temp_path_of(source_file_path)
        # 临时目录为空就解压原文件
        if not extract_path.exists() or not list(extract_path.iterdir()):
            ZipUtil.decompress_zip_to_path(source_file_path, extract_path)

        # 由于ebook给的相对路径与epub解压后路径是不准 遍历文件夹中的所有文件,找到文件
        book_file_dict = self._get_book_file_dict(extract_path)
        book = epub.read_epub(source_file_path)
        for item in book.get_items():
            # 检查是否是文本内容
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                item_id = item.get_id()
                file_name = Path(item.get_name()).name
                if item_id in content and file_name in book_file_dict:
                    book_file_dict[file_name].write_text(content[item_id], encoding='utf-8')
        ZipUtil.compress_to_zip_file(extract_path, write_file_path)

    def clear_temp(self, file_path: Path, temp_root: Path = None):
        extract_path = temp_root if temp_root else self.temp_path_of(file_path)
        if extract_path.exists():
            shutil.rmtree(extract_path)

    def _get_book_file_dict(self, extract_path: Path):
        return {
            file: root / file
            for root, _, files in extract_path.walk() for file in files
        }
