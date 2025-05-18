import zipfile
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, PageElement, Tag

from ModuleFolders.FileAccessor import ZipUtil


class DocxAccessor:

    def read_content(self, source_file_path: Path):
        with zipfile.ZipFile(source_file_path) as zipf:
            content = zipf.read("word/document.xml").decode("utf-8")
        # 读取xml内容
        xml_soup = BeautifulSoup(content, 'xml')

        # 遍历每个段落并合并相邻且格式相同的 run
        for paragraph in xml_soup.find_all('w:p', recursive=True):
            self._merge_adjacent_same_style_run(paragraph)
        return xml_soup

    def write_content(
        self, content: BeautifulSoup, write_file_path: Path,
        source_file_path: Path,
    ):
        ZipUtil.replace_in_zip_file(
            source_file_path, write_file_path, {"word/document.xml": str(content)}
        )

    def _get_style(self, run: Tag):
        rpr = run.find("w:rPr")
        if not rpr:
            return {}
        return {
            tag.name: tag.attrs for tag in rpr.find_all(recursive=False)
        }

    def _is_tag_of(self, ele: PageElement, tag_name: str):
        return isinstance(ele, Tag) and ele.name == tag_name

    def _is_empty_string(self, ele: PageElement):
        return isinstance(ele, NavigableString) and ele.strip() == ""

    def _merge_adjacent_same_style_run(self, paragraph: Tag):

        # 排除掉语法检测和空字符串
        child_nodes = [
            ele for ele in paragraph.children
            if not self._is_tag_of(ele, "proofErr") and not self._is_empty_string(ele)
        ]
        new_children = []
        i = 0
        n = len(child_nodes)

        while i < n:
            current = child_nodes[i]

            # 如果不是run节点，直接保留
            if not self._is_tag_of(current, "r"):
                new_children.append(current)
                i += 1
                continue
            # 如果是 run 节点，但是没有文本内容也直接保留
            elif not (current_text := current.find("w:t")) or current_text.string is None:
                new_children.append(current)
                i += 1
                continue

            # 如果是run节点，尝试合并后续相同格式的run
            merged_run = current
            j = i + 1
            while j < n:
                next_node = child_nodes[j]

                # 遇到其他类型节点，停止合并
                if not self._is_tag_of(current, "r"):
                    break

                # 格式相同则合并文本内容
                if self._get_style(merged_run) == self._get_style(next_node):
                    current_t = merged_run.find("w:t")
                    next_t = next_node.find("w:t")
                    if next_t:
                        if next_t.get("xml:space") == "preserve":
                            current_t["xml:space"] = "preserve"
                        current_t.string += next_t.get_text()
                    j += 1
                else:
                    break
            new_children.append(merged_run)
            i = j  # 跳过已处理的节点

        # 用重构后的子节点列表替换原始内容
        paragraph.clear()
        for node in new_children:
            paragraph.append(node)
