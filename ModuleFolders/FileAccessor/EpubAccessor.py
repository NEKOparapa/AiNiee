import posixpath
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

from ModuleFolders.FileAccessor import ZipUtil


class EpubAccessor:

    def read_content(self, source_file_path: Path):
        with zipfile.ZipFile(source_file_path, 'r') as zipf:
            meta_content = zipf.read("META-INF/container.xml")
            meta_soup = BeautifulSoup(meta_content, "xml")
            opf_file = None

            for root_file in meta_soup.select('container rootfiles rootfile'):
                if root_file.get("media-type") == "application/oebps-package+xml":
                    opf_file = root_file.get("full-path")
            if opf_file is None:
                return []
            items = []
            opf_soup = BeautifulSoup(zipf.read(opf_file), "xml")
            files = {x.filename: x for x in zipf.infolist()}
            for item in opf_soup.select("manifest item"):
                # 检查是否是文本内容，且文件存在压缩包内
                filename = posixpath.join(posixpath.dirname(opf_file), item["href"])
                if item.get("media-type") == "application/xhtml+xml" and filename in files:
                    content = zipf.read(files[filename]).decode("utf-8")
                    items.append((item["id"], filename, content))
            return items

    def write_content(
        self, content: dict[str, str], write_file_path: Path,
        source_file_path: Path,
    ):
        ZipUtil.replace_in_zip_file(source_file_path, write_file_path, content)
