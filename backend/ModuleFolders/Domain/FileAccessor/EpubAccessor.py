import posixpath
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

from ModuleFolders.Domain.FileAccessor import ZipUtil


class EpubAccessor:

    def _find_opf_path(self, zipf: zipfile.ZipFile) -> str | None:
        """从 container.xml 中解析 OPF 文件路径。"""
        meta_content = zipf.read("META-INF/container.xml")
        meta_soup = BeautifulSoup(meta_content, "xml")
        for root_file in meta_soup.select('container rootfiles rootfile'):
            if root_file.get("media-type") == "application/oebps-package+xml":
                return root_file.get("full-path")
        return None

    def read_content(self, source_file_path: Path):
        """读取 EPUB 中的内容文件（XHTML、NCX）和 OPF 元数据文件。

        Returns:
            tuple: (items, opf_info)
                - items: list of (item_id, filename, content) for XHTML/NCX files
                - opf_info: (opf_filename, opf_content) or None
        """
        with zipfile.ZipFile(source_file_path, 'r') as zipf:
            opf_file = self._find_opf_path(zipf)
            if opf_file is None:
                return [], None
            items = []
            opf_content = zipf.read(opf_file).decode("utf-8")
            opf_soup = BeautifulSoup(opf_content, "xml")
            files = {x.filename: x for x in zipf.infolist()}

            for item in opf_soup.select("manifest item"):
                filename = posixpath.join(posixpath.dirname(opf_file), item["href"])
                media_type = item.get("media-type")

                # 检查文件是否存在于压缩包内
                if filename not in files:
                    continue

                # XHTML 内容文件
                if media_type == "application/xhtml+xml":
                    content = zipf.read(files[filename]).decode("utf-8")
                    items.append((item["id"], filename, content))
                # NCX 目录文件（toc.ncx）
                elif media_type == "application/x-dtbncx+xml":
                    content = zipf.read(files[filename]).decode("utf-8")
                    items.append((item["id"], filename, content))

            return items, (opf_file, opf_content)

    def write_content(
        self, content: dict[str, str], write_file_path: Path,
        source_file_path: Path,
    ):
        ZipUtil.replace_in_zip_file(source_file_path, write_file_path, content)
