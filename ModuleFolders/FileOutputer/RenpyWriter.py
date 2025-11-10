import re
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)

class RenpyWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    @classmethod
    def get_project_type(self):
        return ProjectType.RENPY

    def _is_escaped_quote(self, text: str, pos: int) -> bool:
        """
        检查指定位置的引号是否被转义。
        """
        if pos == 0:
            return False
        
        backslash_count = 0
        check_pos = pos - 1
        
        while check_pos >= 0 and text[check_pos] == '\\':
            backslash_count += 1
            check_pos -= 1
        
        return backslash_count % 2 == 1

    def _find_first_unescaped_quote(self, text: str, start: int = 0) -> int:
        """
        从前往后查找第一个未转义的双引号。
        """
        pos = start
        while pos < len(text):
            if text[pos] == '"' and not self._is_escaped_quote(text, pos):
                return pos
            pos += 1
        return -1

    def _find_last_unescaped_quote(self, text: str) -> int:
        """
        从后往前查找最后一个未转义的双引号。
        """
        pos = len(text) - 1
        while pos >= 0:
            if text[pos] == '"' and not self._is_escaped_quote(text, pos):
                return pos
            pos -= 1
        return -1

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        lines = source_file_path.read_text(encoding="utf-8").splitlines(True)
        new_items = sorted(cache_file.items, key=lambda x: x.require_extra("new_line_num"), reverse=True)

        for item in new_items:
            line_num = item.require_extra("new_line_num")
            if line_num < 0 or line_num >= len(lines):
                print(f"警告: 项目的行号 {line_num} 无效。正在跳过。")
                continue

            original_line = lines[line_num]
            new_trans = self._escape_quotes_for_renpy(item.final_text)
            
            # 精确定位要替换的文本范围
            tag = item.require_extra("tag")
            
            # 默认搜索起点为0
            search_start_index = 0
            if tag:
                # 如果有标签，则从标签结束后开始搜索第一个引号，以处理 Character("xxx") "..." 格式
                try:
                    tag_start_index = original_line.find(tag)
                    if tag_start_index != -1:
                        search_start_index = tag_start_index + len(tag)
                except Exception:
                    pass

            # 使用改进的查找方法，跳过转义的引号
            first_quote_index = self._find_first_unescaped_quote(original_line, search_start_index)
            last_quote_index = self._find_last_unescaped_quote(original_line)

            if first_quote_index != -1 and last_quote_index > first_quote_index:
                prefix = original_line[:first_quote_index + 1]
                suffix = original_line[last_quote_index:]
                new_line = f'{prefix}{new_trans}{suffix}'
                lines[line_num] = new_line
            else:
                print(f"警告: 无法在行 {line_num} 中为项目找到有效的引号对。原始内容:\n{original_line}")

        translation_file_path.parent.mkdir(parents=True, exist_ok=True)
        translation_file_path.write_text("".join(lines), encoding="utf-8")

    def _escape_quotes_for_renpy(self, text: str) -> str:
        """
        - 保留已经转义的 `\"`。
        - 保留空的双引号 `""`。
        - 保留带空格的双引号 `" "`。
        - 将所有其他 `"` 转义为 `\"`。
        """
        pattern = r'\\\"|\"\"|\" \"|\"'

        def replacer(match):
            matched_text = match.group(0)
            if matched_text in ('\\"', '""', '" "'):
                return matched_text
            elif matched_text == '"':
                return '\\"'
            return matched_text

        return re.sub(pattern, replacer, text)