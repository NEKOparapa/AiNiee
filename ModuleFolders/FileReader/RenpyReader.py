import re
from pathlib import Path
from typing import List, Optional, Tuple

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)

class RenpyReader(BaseSourceReader):
    """
    读取 rpy 文件并提取翻译条目，支持下面格式:
    1. old "..." / new "..."
    2. # tag "..." / tag "..."
    3. # "..." / "..."
    4. # Character("xxx") "..." / Character("xxx") "..."
    5. # bri.c "..." / bri.c "..."
    """
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.RENPY

    @property
    def support_file(self):
        return "rpy"

    # 用于检查行是否以翻译注释行格式开头的正则表达式
    COMMENT_TRANSLATION_START_PATTERN = re.compile(r"^\s*#\s*")

    # 检查指定位置的引号是否被转义。
    def _is_escaped_quote(self, text: str, pos: int) -> bool:
        """
        检查指定位置的引号是否被转义。
        通过计算引号前面连续反斜杠的数量来判断：
        - 偶数个反斜杠（包括0）：引号未被转义
        - 奇数个反斜杠：引号被转义
        
        """
        if pos == 0:
            return False
        
        backslash_count = 0
        check_pos = pos - 1
        
        # 向前计算连续的反斜杠数量
        while check_pos >= 0 and text[check_pos] == '\\':
            backslash_count += 1
            check_pos -= 1
        
        # 奇数个反斜杠表示引号被转义
        return backslash_count % 2 == 1

    # 从后往前查找最后一个未转义的双引号。
    def _find_last_unescaped_quote(self, text: str, end: int = -1) -> int:
        """
        从后往前查找最后一个未转义的双引号。
        
        """
        if end == -1:
            end = len(text)
        
        pos = end - 1
        while pos >= 0:
            if text[pos] == '"' and not self._is_escaped_quote(text, pos):
                return pos
            pos -= 1
        
        return -1

    # 从前往后查找第一个未转义的双引号。
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

    # 从一行中分离出标签（前缀）和引用的文本。
    def _get_dialogue_parts(self, line: str) -> Optional[Tuple[str, str]]:
        """
        从一行中分离出标签（前缀）和引用的文本。
        通过从后往前查找未转义的引号，可以准确处理含有转义引号的文本。
        
        """
        # 1. 找到最后一个未转义的引号，这是对话的结束引号
        last_quote_index = self._find_last_unescaped_quote(line)
        if last_quote_index == -1:
            return None

        # 2. 在最后一个引号之前的部分中，反向查找第一个未转义的引号，这是对话的开始引号
        first_quote_index = self._find_last_unescaped_quote(line, last_quote_index)
        
        # 如果找不到开始的引号，或者引号对无效
        if first_quote_index == -1:
            # 处理只有引号没有标签的情况，例如 '"...'
            if line.strip().startswith('"'):
                first_quote_index = self._find_first_unescaped_quote(line)
                if first_quote_index >= last_quote_index:
                    return None
            else:
                return None

        # 标签是对话开始引号之前的所有内容
        tag = line[:first_quote_index].strip()
        # 文本是两个对话引号之间的内容
        text = line[first_quote_index + 1:last_quote_index]
        
        return tag, text

    def _find_next_relevant_line(self, lines: List[str], start_index: int) -> Optional[Tuple[int, str]]:
        """
        从指定索引开始，查找下一个有效的 Ren'Py 代码对话行。
        一个有效的代码行是任何可以通过 `_get_dialogue_parts` 成功解析的行。
        它会主动跳过空行、非对话注释、以及不符合翻译格式的指令。
        """
        for i in range(start_index, len(lines)):
            line = lines[i]
            stripped = line.strip()

            # 如果遇到下一个翻译块的定义，停止搜索
            if stripped.startswith("translate "):
                return None

            # 尝试将该行解析为对话部分，如果成功，则为相关行
            if self._get_dialogue_parts(stripped) is not None:
                return i, line

        return None # 如果直到文件末尾都没找到，返回 None

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        lines = file_path.read_text(encoding=pre_read_metadata.encoding).splitlines()
        entries = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # --- 格式 1: old / new ---
            if stripped.startswith("old "):
                parts = self._get_dialogue_parts(stripped)
                if parts:
                    source = parts[1]
                    found_new = False
                    for j in range(i + 1, len(lines)):
                        next_line = lines[j]
                        next_stripped = next_line.strip()
                        if next_stripped.startswith("new "):
                            new_parts = self._get_dialogue_parts(next_stripped)
                            if new_parts:
                                translated = new_parts[1]
                                entries.append({
                                    "source": source,
                                    "translated": translated,
                                    "new_line_num": j,
                                    "format_type": "old_new",
                                    "tag": None
                                })
                                i = j
                                found_new = True
                                break
                        elif next_stripped.startswith("old ") or self.COMMENT_TRANSLATION_START_PATTERN.match(next_stripped) or self._get_dialogue_parts(next_stripped):
                            break
                    if not found_new:
                        pass
                i += 1

            # --- 格式 2, 3, 4, 5: 注释行后跟代码行 ---
            elif self.COMMENT_TRANSLATION_START_PATTERN.match(stripped):
                comment_line = line
                
                # 从 '#' 后提取潜在的源对话行
                potential_source_line = comment_line.split('#', 1)[-1].lstrip()
                comment_parts = self._get_dialogue_parts(potential_source_line)

                # 确保它不是元数据注释（如 # game/script.rpy:123）
                is_meta_comment = potential_source_line.startswith("game/") or potential_source_line.startswith("renpy/")
                
                if comment_parts and not is_meta_comment:
                    comment_tag, comment_source = comment_parts
                    
                    # 查找下一个相关的代码行
                    next_line_info = self._find_next_relevant_line(lines, i + 1)
                    
                    if next_line_info:
                        code_line_num, code_line = next_line_info
                        code_parts = self._get_dialogue_parts(code_line.strip())
                        
                        if code_parts:
                            code_tag, code_text = code_parts
                            
                            # 【核心验证】确保注释行和代码行的标签完全一致
                            if comment_tag == code_tag:
                                entries.append({
                                    "source": comment_source,
                                    "translated": code_text,
                                    "new_line_num": code_line_num,
                                    "format_type": "comment_dialogue", # 统一格式类型
                                    "tag": code_tag # 存储标签以供写入器使用
                                })
                                i = code_line_num + 1
                                continue

                # 如果不是有效的翻译对，则正常递增
                i += 1
            else:
                # 如果没有模式匹配或处理，则默认增加
                i += 1

        # 转换为 CacheItem 对象
        items = []
        for entry in entries:
            extra = {
                "new_line_num": entry["new_line_num"],
                "format_type": entry["format_type"],
                "tag": entry.get("tag"),
            }
            item = CacheItem(source_text=entry["source"], translated_text=entry["translated"], extra=extra)
            items.append(item)
        return CacheFile(items=items)