import re
from collections import Counter
from pathlib import Path

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)

class RenpyWriter(BaseTranslatedWriter):
    """
    Ren'Py 翻译文件写入器。
    """
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
    
    def _escape_quotes_for_renpy(self, text: str) -> str:
        """转义文本内的双引号，保留 \"、"" 和 " "。"""
        pattern = r'\\\"|\"\"|\" \"|\"'
        def replacer(match):
            matched_text = match.group(0)
            if matched_text in ('\\"', '""', '" "'):
                return matched_text
            elif matched_text == '"':
                return '\\"'
            return matched_text
        return re.sub(pattern, replacer, text)

    def _find_interpolation_end(self, text: str, start: int) -> int:
        """查找变量的右括号，支持下标嵌套和表达式中的字符串。"""
        depth = 1
        quote = None
        pos = start + 1
        while pos < len(text):
            char = text[pos]
            if quote:
                if char == "\\":
                    pos += 2
                    continue
                if text.startswith(quote, pos):
                    pos += len(quote)
                    quote = None
                    continue
            elif char in ("'", '"'):
                quote = char * 3 if text.startswith(char * 3, pos) else char
                pos += len(quote)
                continue
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return pos
            pos += 1
        return -1

    def _extract_name_variables(self, name: str) -> Counter[str] | None:
        """统计完整变量（包括格式标记）；括号未闭合时返回 None。"""
        variables = Counter()
        pos = 0
        while pos < len(name):
            if name[pos] != "[":
                pos += 1
                continue
            # Ren'Py 用 [[ 表示字面的左方括号，不是变量。
            if name.startswith("[[", pos):
                pos += 2
                continue
            end_pos = self._find_interpolation_end(name, pos)
            if end_pos == -1:
                return None
            variables[name[pos:end_pos + 1]] += 1
            pos = end_pos + 1
        return variables

    def _separate_name_and_text(
        self, text: str, original_name: str | None = None,
    ) -> tuple[str | None, str]:
        """
        从翻译文本开头分离人名与正文，只处理开头的 [人名] 或 【人名】。
        跳过人名中的完整变量，匹配外层括号，并去除正文开头的一个空格。
        """
        opener = text[:1]
        closer = {"[": "]", "【": "】"}.get(opener)
        if closer is None:
            return None, text

        # 人名未变时直接使用已知边界，也避免字面方括号产生歧义。
        if original_name:
            prefix = f"{opener}{original_name}{closer}"
            if text.startswith(prefix):
                return original_name, text[len(prefix):].removeprefix(" ")

        depth = 1
        pos = 1
        while pos < len(text):
            char = text[pos]
            if char == "[":
                variable_end = self._find_interpolation_end(text, pos)
                if variable_end == -1:
                    return None, text
                pos = variable_end + 1
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    if pos > 1:  # 排除空名字 [] / 【】
                        return text[1:pos], text[pos + 1:].removeprefix(" ")
                    break
            pos += 1
        return None, text

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

            # 如果翻译状态为 EXCLUDED(7)，强制使用原文；否则按默认优先级(润色>翻译>原文)
            if getattr(item, "translation_status", None) == TranslationStatus.EXCLUDED:
                full_translated_text = item.source_text
            else:
                full_translated_text = item.final_text
            
            # --- 1. 分离名字和内容 ---
            
            # 只有当 Reader 阶段明确提取了名字（original_name 不为 None），我们才去尝试分离
            # 这可以防止把原文中自带的 [System]... 当作我们添加的 Tag 被切掉
            original_name_extracted = item.get_extra("original_name")
            
            trans_name = None
            trans_msg = full_translated_text

            if original_name_extracted:
                extracted_name, extracted_msg = self._separate_name_and_text(
                    full_translated_text, original_name_extracted,
                )
                if extracted_name is not None:
                    trans_name = extracted_name
                    trans_msg = extracted_msg
                elif full_translated_text.startswith(("[", "【")):
                    # 无法可靠定位正文时，不把损坏的人名前缀写入对白。
                    print(f"警告: {source_file_path}:{line_num + 1} 人名括号不完整或为空，保留原始行。")
                    continue
                else:
                    print(f"警告: {source_file_path}:{line_num + 1} 无法分离译文人名，保留原人名。")

            # --- 2. 转义文本 ---
            new_trans_msg = self._escape_quotes_for_renpy(trans_msg)
            
            # --- 3. 定位原始行结构 ---
            tag = item.require_extra("tag")
            search_start_index = 0
            if tag:
                try:
                    tag_start_index = original_line.find(tag)
                    if tag_start_index != -1:
                        search_start_index = tag_start_index + len(tag)
                except Exception:
                    pass

            first_quote_index = self._find_first_unescaped_quote(original_line, search_start_index)
            last_quote_index = self._find_last_unescaped_quote(original_line)

            if first_quote_index != -1 and last_quote_index > first_quote_index:
                prefix_part = original_line[:first_quote_index + 1] # 含左引号
                suffix_part = original_line[last_quote_index:]      # 含右引号及后缀
                
                # --- 4. 智能名字回填 ---
                # 条件：
                # A. 名字被标记为需要翻译 (Reader 中判断为字符串或 Character 函数)
                # B. 我们成功提取到了新的翻译名字
                # C. 我们知道原始名字是什么
                if item.get_extra("name_is_translated") and trans_name and original_name_extracted:
                    original_variables = self._extract_name_variables(original_name_extracted)
                    translated_variables = self._extract_name_variables(trans_name)
                    if original_variables is not None and translated_variables == original_variables:
                        prefix_part = prefix_part.replace(original_name_extracted, trans_name)
                    else:
                        print(f"警告: {source_file_path}:{line_num + 1} 译文人名变量不完整或发生变化，保留原人名。")

                new_line = f'{prefix_part}{new_trans_msg}{suffix_part}'
                lines[line_num] = new_line
            else:
                print(f"警告: 无法在行 {line_num} 中找到有效的引号对。原始内容:\n{original_line}")

        translation_file_path.parent.mkdir(parents=True, exist_ok=True)
        translation_file_path.write_text("".join(lines), encoding="utf-8")
