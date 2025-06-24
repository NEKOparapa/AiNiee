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

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        # 读取行，保留换行符
        lines = source_file_path.read_text(encoding="utf-8").splitlines(True)

        # 按行号降序排序项目，以避免修改期间索引偏移问题
        new_items = sorted(cache_file.items, key=lambda x: x.require_extra("new_line_num"), reverse=True)

        for item in new_items:
            line_num = item.require_extra("new_line_num")  # 这是要修改的行号（'new' 行或代码行）
            if line_num < 0 or line_num >= len(lines):
                print(f"警告: 项目的行号 {line_num} 无效。正在跳过。")
                continue

            original_line = lines[line_num]
            new_trans = item.final_text # 最终文本

            # 只转义单个双引号
            new_trans = self._escape_quotes_for_renpy(item.final_text)

            # 查找原始行中第一个和最后一个双引号的索引
            first_quote_index = original_line.find('"')
            last_quote_index = original_line.rfind('"')

            # 确保我们找到了不同的开始和结束引号
            if first_quote_index != -1 and last_quote_index != -1 and first_quote_index < last_quote_index:
                # 提取第一个引号之前的部分（包括缩进、标签等）
                prefix = original_line[:first_quote_index + 1]
                # 提取最后一个引号之后的部分（包括尾随空格、注释等）
                suffix = original_line[last_quote_index:]

                # 通过仅替换引号内的内容来构造新行
                new_line = f'{prefix}{new_trans}{suffix}'
                lines[line_num] = new_line

        # 将修改后的行写回到翻译文件路径
        translation_file_path.parent.mkdir(parents=True, exist_ok=True) # 确保目录存在
        translation_file_path.write_text("".join(lines), encoding="utf-8")



    def _escape_quotes_for_renpy(self, text: str) -> str:
        """
        - 保留已经转义的 `\"`。
        - 保留空的双引号 `""`。
        - 保留带空格的双引号 `" "`。
        - 将所有其他 `"` 转义为 `\"`。
        """
        # 正则表达式匹配以下任意一种情况：
        # 1. `\\\"`: 一个已经转义的双引号
        # 2. `\"\"`: 两个连续的双引号
        # 3. `\" \"`: 一个带空格的双引号
        # 4. `\"`: 单个双引号
        # re.sub 会从左到右匹配，所以 `\\"` 会优先于 `"` 被匹配。
        pattern = r'\\\"|\"\"|\" \"|\"'

        def replacer(match):
            """定义替换逻辑"""
            matched_text = match.group(0)
            # 如果匹配到的是特殊情况，则原样返回，不进行任何修改
            if matched_text in ('\\"', '""', '" "'):
                return matched_text
            # 否则，匹配到的是需要转义的单个双引号
            elif matched_text == '"':
                return '\\"'
            # 理论上不会走到这里，但作为保障
            return matched_text

        return re.sub(pattern, replacer, text)