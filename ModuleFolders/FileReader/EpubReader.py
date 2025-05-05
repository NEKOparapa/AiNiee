import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag, NavigableString


from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileAccessor.EpubAccessor import EpubAccessor
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class EpubReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)
        self.file_accessor = EpubAccessor()

    @classmethod
    def get_project_type(cls):
        return ProjectType.EPUB

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
        ("blockquote", r"<blockquote[^>]*>(.*?)</blockquote>", []),
        ("td", r"<td[^>]*>(.*?)</td>", []),

        # div标签要放在最后面，这是提取不到前面任何文本内容再考虑的标签
        ("div", r"<div[^>]*>(.*?)</div>", ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'text', 'blockquote', 'td']),
    ]

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:

        items = []
        for item_id, _, html_content in self.file_accessor.read_content(file_path):
            for tag_type, pattern, forbidden_tags in self.TAG_PATTERNS_LIST:
                # 使用 finditer 查找所有匹配项，可以迭代处理
                for match in re.finditer(pattern, html_content, re.DOTALL):
                    html_text = match.group(0)  # 完整匹配到的HTML标签

                    # 处理多层嵌套标签的情况，找到存储文本内容的标签
                    tag_type, html_text = self.extract_epub_content_refined(html_text)
                    if not html_text: 
                        continue

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
                    extra = {
                        "original_html": html_text,
                        "tag_type": tag_type,
                        "item_id": item_id,
                    }
                    items.append(CacheItem(source_text=text_content, extra=extra))
        return CacheFile(items=items)

    # 提取最内层包含文本的标签及其内容（改进点：可以考虑保留部分标签的内容，比如span）
    def extract_epub_content_refined(self,html_string: str) :
        """
        从HTML字符串中提取最内层包含实际内容的标签及其原始字符串
        
        参数:
            html_string: 待解析的HTML片段字符串
            
        返回:
            元组(标签名, 标签原始完整字符串) 或 (None, None)
            保持原始字符串中的属性顺序和格式
        """
        if not html_string or not html_string.strip():
            return None, None

        # 首先用BeautifulSoup分析结构
        soup = BeautifulSoup(html_string.strip(), 'html.parser')
        
        # 查找第一个实际标签
        top_tag = None
        for element in soup.contents:
            if isinstance(element, Tag):
                top_tag = element
                break

        if not top_tag:
            return None, None

        # 迭代查找最具体的标签
        current_tag = top_tag
        while True:
            text_containing_children = []
            for child in current_tag.children:
                has_meaningful_text = False
                if isinstance(child, NavigableString):
                    if child.strip():
                        has_meaningful_text = True
                elif isinstance(child, Tag):
                    if child.get_text(strip=True):
                        has_meaningful_text = True

                if has_meaningful_text:
                    text_containing_children.append(child)

            num_text_children = len(text_containing_children)

            if num_text_children == 1:
                the_child = text_containing_children[0]
                if isinstance(the_child, Tag):
                    current_tag = the_child
                    continue
                else:
                    break
            else:
                break

        # 获取标签在原始字符串中的位置
        original_html = html_string.strip()
        tag_name = current_tag.name
        
        # 构建正则表达式匹配原始标签
        # 匹配开始标签（包括所有属性）
        start_tag_pattern = re.compile(
            r'<{0}[^>]*>'.format(tag_name), 
            re.IGNORECASE
        )
        
        # 匹配整个标签（包括内容）
        full_tag_pattern = re.compile(
            r'<{0}[^>]*>.*?</{0}>'.format(tag_name), 
            re.IGNORECASE | re.DOTALL
        )
        
        # 在原始HTML中查找匹配
        start_tag_match = start_tag_pattern.search(original_html)
        if not start_tag_match:
            return current_tag.name, str(current_tag)  # 回退到BeautifulSoup生成
        
        # 从匹配位置开始查找完整标签
        remaining_html = original_html[start_tag_match.start():]
        full_tag_match = full_tag_pattern.search(remaining_html)
        
        if full_tag_match:
            original_tag = full_tag_match.group(0)
            return tag_name, original_tag
        else:
            # 如果正则匹配失败，回退到BeautifulSoup生成
            return current_tag.name, str(current_tag)