import re
from pathlib import Path

from bs4 import BeautifulSoup

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileAccessor.EpubAccessor import EpubAccessor
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class EpubReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)
        self.file_accessor = EpubAccessor()

    @classmethod
    def get_project_type(cls):
        return "Epub"

    @property
    def support_file(self):
        return 'epub'

    # 正则字典，只包含成对标签，暂不考虑自闭合标签
    TAG_PATTERNS_LIST = [
        ("p", r"<p[^>]*>(.*?)</p>", []),
        ("heading", r"<h[1-7][^>]*>(.*?)</h[1-7]>", []),

        # 有些p标签内容嵌套在li标签里面,
        ("li", r"<li[^>]*>(.*?)</li>", ['p']),
        ("text", r"<text[^>]*>(.*?)</text>", []),

        # div标签要放在最后面，这是提取不到前面任何文本内容再考虑的标签
        ("div", r"<div[^>]*>(.*?)</div>", ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'text']),
    ]

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:

        items = []
        for item_id, html_content in self.file_accessor.read_content(file_path).items():
            for tag_type, pattern, forbidden_tags in self.TAG_PATTERNS_LIST:
                # 使用 finditer 查找所有匹配项，可以迭代处理
                for match in re.finditer(pattern, html_content, re.DOTALL):
                    html_text = match.group(0)  # 完整匹配到的HTML标签

                    # 提取纯文本，并处理嵌套标签
                    soup = BeautifulSoup(html_text, 'html.parser')
                    text_content = soup.get_text(strip=True)

                    if not text_content:  # 检查一下是否提取到空文本内容
                        continue

                    if forbidden_tags:
                        # 检查是否包含禁止的子标签
                        forbidden_soup_elemnt = soup.find(forbidden_tags)
                        if forbidden_soup_elemnt is not None:
                            continue

                    item = text_to_cache_item(text_content)
                    item.original_html = html_text
                    item.tag_type = tag_type  # 直接使用循环的 tag_type
                    item.item_id = item_id
                    items.append(item)
        self.file_accessor.clear_temp(file_path)
        return items
