import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from ModuleFolders.Infrastructure.Cache.CacheFile import CacheFile
from ModuleFolders.Infrastructure.Cache.CacheItem import CacheItem
from ModuleFolders.Infrastructure.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)

class RenpyReader(BaseSourceReader):
    """
    读取 rpy 文件并提取翻译条目，支持下面格式:
    1. old "..." / new "..." , ...是原文文本，无人名信息,人名不需要翻译
    2. # tag "..." / tag "..." , ...是原文文本，tag是人名代号,人名不需要翻译
    3. # "..." / "..." , ...是原文文本，无人名信息,人名不需要翻译
    4. # Character("xxx") "..." / Character("xxx") "..."  , ...是原文文本，xxx是人名信息，人名需要翻译
    5. # bri.c "..." / bri.c "..." , ...是原文文本，bri.c是人名代号,人名不需要翻译
    6. # "xxx" "..." / # "xxx" "..."  , ...是原文文本，xxx是人名信息，人名需要翻译
    7. # "yyy"yyy"yyy" / # "yyy"yyy"yyy"  , yyy"yyy"yyy是原文文本，无人名信息，人名不需要翻译
    8. # tag ""yyy",yyy"yyy"" / tag ""yyy",yyy"yyy""  , "yyy",yyy"yyy"是原文文本，tag 是人名代号，人名不需要翻译
    9. # tag "\"yyy\"" / # tag "\"yyy\""  , \"yyy\"是原文文本，带转义双引号，tag 是人名代号，人名不需要翻译
    *. 支持中间夹杂 voice 语句的格式，并跳过 voice 语句
    """
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.RENPY

    @property
    def support_file(self):
        return "rpy"

    # 正则表达式定义
    COMMENT_TRANSLATION_START_PATTERN = re.compile(r"^\s*#\s*")
    CHARACTER_FUNC_PATTERN = re.compile(r'^Character\(\s*"([^"]+)"')
    STRING_LITERAL_PATTERN = re.compile(r'^"([^"]+)"$')

    def _is_escaped_quote(self, text: str, pos: int) -> bool:
        """检查指定位置的引号是否被转义。"""
        if pos == 0:
            return False
        backslash_count = 0
        check_pos = pos - 1
        while check_pos >= 0 and text[check_pos] == '\\':
            backslash_count += 1
            check_pos -= 1
        return backslash_count % 2 == 1

    def _find_last_unescaped_quote(self, text: str, end: int = -1) -> int:
        """从后往前查找最后一个未转义的双引号。"""
        if end == -1:
            end = len(text)
        pos = end - 1
        while pos >= 0:
            if text[pos] == '"' and not self._is_escaped_quote(text, pos):
                return pos
            pos -= 1
        return -1

    def _find_first_unescaped_quote(self, text: str, start: int = 0) -> int:
        """从前往后查找第一个未转义的双引号。"""
        pos = start
        while pos < len(text):
            if text[pos] == '"' and not self._is_escaped_quote(text, pos):
                return pos
            pos += 1
        return -1

    def _get_dialogue_parts(self, line: str) -> Optional[Tuple[Optional[str], str]]:
        """
        从一行代码中解析 [标签] 和 [文本]。
        
        逻辑改进：
        为了区分 'Tag "Text"' 和 '"Text with "quotes" inside"', 
        我们检查倒数第二个引号前面是否是空格。
        
        返回: (Tag, Text) 或 (None, Text) 或 None(解析失败)
        """
        # 1. 找到最后一个引号（潜在的文本结束符）
        last_quote_index = self._find_last_unescaped_quote(line)
        if last_quote_index == -1:
            return None

        # 2. 找到倒数第二个引号（潜在的文本开始符）
        start_quote_index = self._find_last_unescaped_quote(line, last_quote_index)
        
        is_valid_split = False
        
        if start_quote_index != -1:
            # 如果 start_quote_index 为 0，说明整行以引号开头 (如 "Text")，这是有效的（Tag为None或空）
            if start_quote_index == 0:
                is_valid_split = True
            else:
                # 检查引号前的一个字符
                char_before = line[start_quote_index - 1]
                # Ren'Py 语法要求 Tag 和 "Text" 之间必须有空格分隔
                # 如果引号前是字母（如 "this"），说明这只是文本内部的引用，不是对话开始
                if char_before.isspace():
                    is_valid_split = True
        
        # 3. 路径 A: 成功识别为 [Tag] [Text] 结构
        if is_valid_split:
            tag = line[:start_quote_index].strip()
            text = line[start_quote_index + 1:last_quote_index]
            # 如果 Tag 为空字符串，统一返回 None，方便后续处理
            if not tag:
                return None, text
            return tag, text

        # 4. 路径 B: 切分验证失败，可能是包含内部引号的纯文本行
        # 尝试将整行视为一个文本块：从第一个引号到最后一个引号
        first_quote_from_start = self._find_first_unescaped_quote(line)
        
        if first_quote_from_start != -1 and last_quote_index > first_quote_from_start:
            # 检查引号前是否有内容。如果前面有乱七八糟的内容但没通过上面的 split 检查，可能格式不对，忽略。
            # 如果前面是空的（忽略缩进），则视为无 Tag 的旁白。
            prefix = line[:first_quote_from_start].strip()
            if not prefix:
                text = line[first_quote_from_start + 1 : last_quote_index]
                return None, text # Tag 为 None

        return None

    def _extract_name_info(self, tag: Optional[str]) -> Dict[str, Any]:
        """
        分析 tag，提取上下文信息和翻译策略。
        """
        if not tag:
            return {'name': None, 'should_translate': False}

        # 1. Character("Name") -> 提取 Name，Writer 需回填翻译
        match_char = self.CHARACTER_FUNC_PATTERN.search(tag)
        if match_char:
            return {'name': match_char.group(1), 'should_translate': True}

        # 2. "Name" -> 提取 Name，Writer 需回填翻译
        match_str = self.STRING_LITERAL_PATTERN.match(tag)
        if match_str:
            return {'name': match_str.group(1), 'should_translate': True}

        # 3. 代码变量 (如 bri.c) -> 提取为上下文，但 Writer 不应翻译/修改代码
        return {'name': tag, 'should_translate': False}

    def _find_next_relevant_line(self, lines: List[str], start_index: int) -> Optional[Tuple[int, str]]:
        """查找下一行有效的代码行，跳过 translate 定义等。"""
        for i in range(start_index, len(lines)):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("translate "):
                return None
            if self._get_dialogue_parts(stripped) is not None:
                return i, line
        return None

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
                    source = parts[1] # old 文本
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
                                    "tag": None,
                                    "name_info": None
                                })
                                i = j
                                found_new = True
                                break
                        elif next_stripped.startswith("old ") or self.COMMENT_TRANSLATION_START_PATTERN.match(next_stripped):
                            break
                    if not found_new:
                        pass
                i += 1

            # --- 格式 2: 注释行 + 代码行 ---
            elif self.COMMENT_TRANSLATION_START_PATTERN.match(stripped):
                comment_line = line
                potential_source_line = comment_line.split('#', 1)[-1].lstrip()
                comment_parts = self._get_dialogue_parts(potential_source_line)

                is_meta_comment = potential_source_line.startswith("game/") or potential_source_line.startswith("renpy/")
                
                # 必须成功解析出 parts (即使 Tag 是 None) 且不是元数据注释
                if comment_parts is not None and not is_meta_comment:
                    comment_tag, comment_source = comment_parts
                    
                    if comment_tag == "voice":
                        i += 1
                        continue
                    
                    # 提取人名信息
                    name_data = self._extract_name_info(comment_tag)
                    
                    search_index = i + 1
                    found_match = False
                    
                    while search_index < len(lines):
                        next_line_info = self._find_next_relevant_line(lines, search_index)
                        
                        if not next_line_info:
                            break
                        
                        code_line_num, code_line = next_line_info
                        code_parts = self._get_dialogue_parts(code_line.strip())
                        
                        if code_parts:
                            code_tag, code_text = code_parts
                            
                            if code_tag == "voice":
                                search_index = code_line_num + 1
                                continue
                            
                            # 匹配验证：
                            # 1. 都有 Tag 且相等
                            # 2. 都无 Tag (None == None)
                            if comment_tag == code_tag:
                                entries.append({
                                    "source": comment_source,
                                    "translated": code_text,
                                    "new_line_num": code_line_num,
                                    "format_type": "comment_dialogue",
                                    "tag": code_tag,
                                    "name_info": name_data
                                })
                                i = code_line_num + 1
                                found_match = True
                            break
                        else:
                            break
                    
                    if found_match:
                        continue
                i += 1
            else:
                i += 1

        items = []
        for entry in entries:
            source_text = entry["source"]
            name_data = entry["name_info"]
            extra = {
                "new_line_num": entry["new_line_num"],
                "format_type": entry["format_type"],
                "tag": entry.get("tag"),
                "name_is_translated": False,
                "original_name": None
            }

            # 上下文注入：如果有名字，拼接到原文前
            if name_data and name_data['name']:
                name = name_data['name']
                source_text = f"[{name}]{source_text}"
                extra["original_name"] = name
                extra["name_is_translated"] = name_data['should_translate']

            item = CacheItem(source_text=source_text, translated_text=entry["translated"], extra=extra)
            items.append(item)
        return CacheFile(items=items)