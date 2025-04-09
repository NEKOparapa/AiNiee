from pathlib import Path
from typing import Callable

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig
)


class TxtWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_bilingual_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        self._write_translation_file(translation_file_path, items, self._item_to_bilingual_line)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None
    ):
        self._write_translation_file(translation_file_path, items, self._item_to_translated_line)

    def _write_translation_file(
        self, translation_file_path: Path, items: list[CacheItem],
        item_to_line: Callable[[CacheItem], str],
    ):
        if not items:
            translation_file_path.write_text("", encoding=self.translated_encoding)
            return

        # 处理所有项目，但不添加额外的换行符
        lines = []
        for i, item in enumerate(items):
            if i == len(items) - 1:  # 最后一项
                # 保留原始换行符但不添加额外的换行符
                lines.append(self._item_to_final_line(item, item_to_line))
            else:
                lines.append(item_to_line(item))

        translation_file_path.write_text("".join(lines), encoding=self.translated_encoding)

    def _item_to_final_line(self, item: CacheItem, item_to_line_func: Callable):
        """处理最后一个项目，只保留原始换行符"""
        indent = item.sentence_indent
        # 保留原始换行符
        original_line_break = "\n" * item.line_break if item.line_break > 0 else ""

        if item_to_line_func == self._item_to_bilingual_line:
            return (
                f"{indent}{item.get_source_text().lstrip()}\n"
                f"{indent}{item.get_translated_text().lstrip()}{original_line_break}"
            )
        else:  # item_to_line_func == self._item_to_translated_line
            return f"{indent}{item.get_translated_text().lstrip()}{original_line_break}"

    def _item_to_bilingual_line(self, item: CacheItem):
        # 至少2个换行，让双语排版不那么紧凑
        line_break = "\n" * max(item.line_break + 1, 2)
        indent = item.sentence_indent

        return (
            f"{indent}{item.get_source_text().lstrip()}\n"
            f"{indent}{item.get_translated_text().lstrip()}{line_break}"
        )

    def _item_to_translated_line(self, item: CacheItem):
        line_break = "\n" * (item.line_break + 1)

        return f"{item.sentence_indent}{item.get_translated_text().lstrip()}{line_break}"

    @classmethod
    def get_project_type(self):
        return "Txt"
