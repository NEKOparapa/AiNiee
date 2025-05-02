import shutil
from pathlib import Path
import zipfile

from bs4 import BeautifulSoup

from ModuleFolders.FileAccessor import ZipUtil


class EpubAccessor:
    def __init__(self, temp_folder="EpubCache"):
        self.temp_folder = temp_folder

    def temp_path_of(self, file_path: Path):
        return file_path.parent / self.temp_folder

    def read_content(self, source_file_path: Path, temp_root: Path = None):

        # 解压epub文件到暂存文件夹
        extract_path = temp_root if temp_root else self.temp_path_of(source_file_path)
        ZipUtil.decompress_zip_to_path(source_file_path, extract_path)

        # 由于ebook给的相对路径与epub解压后路径是不准 遍历文件夹中的所有文件
        book_file_dict = self._get_book_file_dict(extract_path)

        # 提取解压后epub文件中的文本内容
        result: dict[str, str] = {}
        for item_id, item_name in self.read_items(source_file_path).items():
            file_name = Path(item_name).name
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

        for item_id, item_name in self.read_items(source_file_path).items():
            file_name = Path(item_name).name
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

    def read_items(self, file_path: Path) -> dict[str, str]:
        with zipfile.ZipFile(file_path, 'r') as zipf:
            meta_content = zipf.read("META-INF/container.xml")
            meta_soup = BeautifulSoup(meta_content, "xml")
            opf_file = None

            for root_file in meta_soup.select('container rootfiles rootfile'):
                if root_file.get("media-type") == "application/oebps-package+xml":
                    opf_file = root_file.get("full-path")
            if opf_file is None:
                return {}
            items = {}
            opf_soup = BeautifulSoup(zipf.read(opf_file), "xml")
            for item in opf_soup.select("manifest item"):
                # 检查是否是文本内容
                if item.get("media-type") == "application/xhtml+xml":
                    items[item["id"]] = item["href"]
            return items
