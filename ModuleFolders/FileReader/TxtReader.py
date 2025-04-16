from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class TxtReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig, max_empty_line_check=None):
        super().__init__(input_config)
        self.max_empty_line_check = max_empty_line_check

    @classmethod
    def get_project_type(cls):
        return "Txt"

    @property
    def support_file(self):
        return "txt"

    # 读取单个txt的文本及其他信息
    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        items = []
        # 切行
        # 使用传入的 `detected_encoding` 参数正确读取未知编码的纯文本文件，并使用`splitlines()`正确切分行
        lines = file_path.read_text(encoding=detected_encoding).splitlines()

        for i, line in enumerate(lines):
            # 如果当前行是空行
            # 并且位置不是文本开头，则跳过当前行
            if not line.strip() and i != 0:
                continue

            # 去掉文本开头的空格
            line_lstrip = line.lstrip()
            # 获取文本行开头的原始空格
            spaces = line[:len(line) - len(line_lstrip)]

            item = text_to_cache_item(line_lstrip)
            # 原始空格保存至变量中，后续Writer中还原
            item.sentence_indent = spaces
            item.line_break = self._count_next_empty_line(lines, i)
            items.append(item)
        return items

    def _count_next_empty_line(self, lines, line_index):
        """检查后续行是否连续空行，最多检查 max_empty_line_check 行"""
        max_empty_line_check = self.max_empty_line_check if self.max_empty_line_check is not None else len(lines)
        empty_line_index = line_index
        for empty_line_index in range(line_index + 1, min(len(lines), line_index + 1 + max_empty_line_check)):
            if lines[empty_line_index].strip() != '':
                empty_line_index -= 1
                break
        return empty_line_index - line_index
