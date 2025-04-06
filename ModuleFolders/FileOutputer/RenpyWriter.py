from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)


# 改进点:现在还没能正确处理文本中含有双引号的问题
class RenpyWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        # 保留换行符
        lines = source_file_path.read_text(encoding="utf-8").splitlines(True)
        new_items = sorted(items, key=lambda x: x.new_line_num, reverse=True)
        for item in new_items:
            line_num = item.new_line_num
            if line_num >= len(lines):
                continue

            new_trans = item.translated_text
            format_type = item.format_type

            if format_type == "old_new":
                old_line = lines[line_num]
                # 保留原格式生成新行
                parts = old_line.split('"', 2)
                if len(parts) >= 3:
                    new_line = f'{parts[0]}"{new_trans}"{parts[2]}'
                    lines[line_num] = new_line
            elif format_type == "comment_tag":
                old_line = lines[line_num]
                tag = item.tag
                # 保留tag生成新行
                parts = old_line.split('"', 1)
                if len(parts) >= 2:
                    new_line = f'    {tag} "{new_trans}{parts[1][len(parts[1].split("\"", 1)[0]):]}'  # fix for tag with space
                    lines[line_num] = new_line

        translation_file_path.write_text("".join(lines), encoding="utf-8")

    @classmethod
    def get_project_type(self):
        return "Renpy"
