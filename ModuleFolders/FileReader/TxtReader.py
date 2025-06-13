from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class TxtReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig, max_empty_line_check=None):
        super().__init__(input_config)
        self.max_empty_line_check = max_empty_line_check

    @classmethod
    def get_project_type(cls):
        return ProjectType.TXT

    @property
    def support_file(self):
        return "txt"

    # 读取单个txt的文本及其他信息
    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        items = []
        # 切行
        # 使用传入的 `detected_encoding` 参数正确读取未知编码的纯文本文件，并使用`splitlines()`正确切分行
        lines = file_path.read_text(encoding=pre_read_metadata.encoding).splitlines()

        for i, line in enumerate(lines):
            # 如果当前行是空行
            # 并且位置不是文本开头，则跳过当前行
            if not line.strip() and i != 0:
                continue

            # 去掉文本开头的BOM
            line_lstrip = line.lstrip("\ufeff")
            extra = {
                "line_break": self._count_next_empty_line(lines, i)
            }
            item = CacheItem(source_text=line_lstrip, extra=extra)

            items.append(item)
        return CacheFile(items=items)

    def _count_next_empty_line(self, lines, line_index):
        """检查后续行是否连续空行，最多检查 max_empty_line_check 行"""
        max_empty_line_check = self.max_empty_line_check if self.max_empty_line_check is not None else len(lines)
        empty_line_index = line_index
        for empty_line_index in range(line_index + 1, min(len(lines), line_index + 1 + max_empty_line_check)):
            if lines[empty_line_index].strip() != '':
                empty_line_index -= 1
                break
        return empty_line_index - line_index
