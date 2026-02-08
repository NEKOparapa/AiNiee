import re
from pathlib import Path

from ModuleFolders.Infrastructure.Cache.CacheFile import CacheFile
from ModuleFolders.Infrastructure.Cache.CacheProject import ProjectType
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

    def _separate_name_and_text(self, text: str) -> tuple[str, str]:
        """
        从翻译文本开头分离人名与正文，只处理开头的 [人名] 或 【人名】。
        处理逻辑：
        1. 必须以 [ 或 【 开头（仅匹配开头）。
        2. 分别以 ] 或 】 作为对应结尾。
        3. 去除 Msg 开头可能由 AI 添加的一个空格。
        """
        # 仅匹配开头的 [人名]
        if text.startswith("["):
            end_pos = text.find("]")
            if end_pos > 1:  # 排除空名字 []
                name = text[1:end_pos]
                msg = text[end_pos + 1:]
                if len(msg) > 0 and msg[0] == ' ':
                    msg = msg[1:]
                return name, msg
        # 仅匹配开头的 【人名】
        if text.startswith("【"):
            end_pos = text.find("】")
            if end_pos > 1:  # 排除空名字 【】
                name = text[1:end_pos]
                msg = text[end_pos + 1:]
                if len(msg) > 0 and msg[0] == ' ':
                    msg = msg[1:]
                return name, msg
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
            full_translated_text = item.final_text
            
            # --- 1. 分离名字和内容 ---
            
            # 只有当 Reader 阶段明确提取了名字（original_name 不为 None），我们才去尝试分离
            # 这可以防止把原文中自带的 [System]... 当作我们添加的 Tag 被切掉
            original_name_extracted = item.get_extra("original_name")
            
            trans_name = None
            trans_msg = full_translated_text

            if original_name_extracted:
                extracted_name, extracted_msg = self._separate_name_and_text(full_translated_text)
                if extracted_name is not None:
                    trans_name = extracted_name
                    trans_msg = extracted_msg
                else:
                    # 分离失败（例如AI把括号删了），保留原文本，不做处理
                    pass

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
                    prefix_part = prefix_part.replace(original_name_extracted, trans_name)

                new_line = f'{prefix_part}{new_trans_msg}{suffix_part}'
                lines[line_num] = new_line
            else:
                print(f"警告: 无法在行 {line_num} 中找到有效的引号对。原始内容:\n{original_line}")

        translation_file_path.parent.mkdir(parents=True, exist_ok=True)
        translation_file_path.write_text("".join(lines), encoding="utf-8")