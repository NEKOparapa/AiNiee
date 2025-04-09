from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item, read_file_safely
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
    def read_source_file(self, file_path: Path, cache_project: CacheProject) -> list[CacheItem]:
        items = []
        # 切行
        # 使用 `BaseReader` 中的 `read_file_safely` 函数正确读取多种编码的文件，并将原始编码与行尾序列保存至 `CacheProject` 类中
        # 可供后续的 `Writer` 使用
        lines = read_file_safely(file_path, cache_project).split(cache_project.get_line_ending())

        for i, line in enumerate(lines):
            # 如果当前行是空行
            # 并且位置不是文本开头，则跳过当前行
            if not line.strip() and i != 0:
                continue

            # 获取文本行开头的原始空格
            spaces = line[:len(line)-len(line.lstrip())]
            item = text_to_cache_item(line)
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
