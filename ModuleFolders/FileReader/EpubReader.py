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
        ("heading", r"<h[1-7]\b[^>]*>(.*?)</h[1-7]>", []),
        ("li", r"<li\b[^>]*>(.*?)</li>", ['p']), # 有些p标签内容嵌套在li标签里
        ("p", r"<p\b[^>]*>(.*?)</p>", []),

        ("blockquote", r"<blockquote\b[^>]*>(.*?)</blockquote>", []),
        ("text", r"<text\b[^>]*>(.*?)</text>", []),
        ("td", r"<td\b[^>]*>(.*?)</td>", []),

        # div标签要放在最后面，这是提取不到前面任何文本内容再考虑的标签
        ("div", r"<div\b[^>]*>(.*?)</div>", ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'li', 'text', 'blockquote', 'td']),
    ]

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:

        items = []
        for item_id, _, html_content in self.file_accessor.read_content(file_path):
            for tag_type, pattern, forbidden_tags in self.TAG_PATTERNS_LIST:
                # 使用 finditer 查找所有匹配项，可以迭代处理
                for match in re.finditer(pattern, html_content, re.DOTALL):
                    html_text_A = match.group(0)  # 完整匹配到的HTML标签

                    # 针对同名嵌套标签内容的处理。正则提取时标签提前闭合，而造成的提取错误。只提取同名子标签的内容，放弃父级标签的内容
                    html_text_B = self.extract_inner_html_from_incomplete_tag(html_text_A)

                    # 处理多层嵌套标签的情况，找到存储文本内容的标签
                    tag_type, html_text_C = self.extract_epub_content_refined(html_text_B)
                    if not html_text_C: 
                        continue

                    # 提取纯文本，并处理嵌套标签
                    soup = BeautifulSoup(html_text_C, 'html.parser')
                    text_content = soup.get_text(strip=True)

                    if not text_content:  # 检查一下是否提取到空文本内容
                        continue

                    if forbidden_tags:
                        # 检查是否包含禁止的子标签
                        forbidden_soup_elemnt = soup.find(forbidden_tags)
                        if forbidden_soup_elemnt is not None:
                            continue
                        
                    extra = {
                        "original_html": html_text_C,
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
        
    # 提取同名嵌套标签的完整子标签内容
    def extract_inner_html_from_incomplete_tag(self,html_string: str) -> str:
        """
        识别残缺的非闭合标签内容，并自动提取第一个符合条件的同名子标签的原始内容。
        如果不是残缺标签，或者没有找到合适的子标签，则返回原内容。
        提取子标签时，使用正则表达式以获取原始字符串内容。

        Args:
            html_string: HTML内容字符串

        Returns:
            处理后的HTML内容 (可能是原始子标签的字符串，或原输入内容)
        """
        # 确定第一个标签的名称
        first_tag_name_match = re.match(rf'<([a-zA-Z][a-zA-Z0-9]*)(?![a-zA-Z0-9\-_])', html_string)
        if not first_tag_name_match:
            # 如果字符串不是以一个可识别的标签开头，则返回原内容
            return html_string

        tag_name = first_tag_name_match.group(1)

        # 构建用于查找开标签和闭标签的正则表达式 (忽略大小写)
        open_tag_pattern = rf'<{tag_name}(?![a-zA-Z0-9\-_])[^>]*>'
        close_tag_pattern = rf'</{tag_name}>'

        # 统计开标签和闭标签的数量
        open_tags_found = re.findall(open_tag_pattern, html_string, re.IGNORECASE)
        close_tags_found = re.findall(close_tag_pattern, html_string, re.IGNORECASE)

        # 如果开标签数量大于闭标签数量，则认为可能是残缺标签
        if len(open_tags_found) > len(close_tags_found):
            # 找到第一个主开标签的结束位置，以便从其后开始搜索子标签
            first_actual_open_tag_match = re.search(open_tag_pattern, html_string, re.IGNORECASE)
            
            if not first_actual_open_tag_match:
                return html_string 
                
            # 从第一个主开标签之后的内容中搜索子标签
            search_start_offset = first_actual_open_tag_match.end()
            remaining_html = html_string[search_start_offset:]

            # 构建正则表达式以查找第一个完整的、同名的子标签
            inner_complete_tag_pattern = rf'(<{tag_name}(?![a-zA-Z0-9\-_])[^>]*>.*?</{tag_name}>)'
            
            match_inner_complete_tag = re.search(
                inner_complete_tag_pattern,
                remaining_html,
                re.DOTALL | re.IGNORECASE  
            )

            if match_inner_complete_tag:
                # 如果找到，返回该子标签的完整原始内容
                return match_inner_complete_tag.group(1)
        
        # 如果标签不是残缺的，或者没有找到符合条件的子标签，则返回原内容
        return html_string
