from pathlib import Path
import re
from typing import List 

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)

class RenpyWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    @classmethod
    def get_project_type(self):
        return "Renpy"

    def write_translated_file(
        self, translation_file_path: Path, items: List[CacheItem], 
        source_file_path: Path = None,
    ):
        # 读取行，保留换行符
        lines = source_file_path.read_text(encoding="utf-8").splitlines(True)

        # 按行号降序排序项目，以避免修改期间索引偏移问题
        new_items = sorted(items, key=lambda x: x.new_line_num, reverse=True)

        for item in new_items:
            line_num = item.new_line_num # 这是要修改的行号（'new' 行或代码行）
            if line_num < 0 or line_num >= len(lines):
                print(f"警告: 项目的行号 {line_num} 无效。正在跳过。")
                continue

            original_line = lines[line_num]
            new_trans = item.translated_text # 新的翻译文本
            new_trans = re.sub(r'(?<!\\)"',r'\\"', new_trans) # 转义双引号

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
        try:
            translation_file_path.parent.mkdir(parents=True, exist_ok=True) # 确保目录存在
            translation_file_path.write_text("".join(lines), encoding="utf-8")
        except Exception as e:
             print(f"写入翻译文件 {translation_file_path} 时出错: {e}")