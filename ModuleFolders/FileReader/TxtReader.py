from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class TxtReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig, max_empty_line_check=2):
        super().__init__(input_config)
        self.max_empty_line_check = max_empty_line_check

    @classmethod
    def get_project_type(cls):
        return "Txt"

    @property
    def support_file(self):
        return "txt"

    def read_source_file(self, file_path: Path) -> list[CacheItem]:
        items = []
        # 切行
        lines = file_path.read_text(encoding='utf-8').split('\n')
        for j, line in enumerate(lines):
            if line.strip() == '':  # 跳过空行
                continue
            spaces = len(line) - len(line.lstrip())  # 获取行开头的空格数
            item = text_to_cache_item(line)
            item.sentence_indent = spaces
            item.line_break = self._count_next_empty_line(lines, j)
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
