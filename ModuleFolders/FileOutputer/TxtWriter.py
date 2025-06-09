from pathlib import Path
from typing import Callable

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class TxtWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def on_write_bilingual(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_translation_file(translation_file_path, cache_file, pre_write_metadata, self._item_to_bilingual_line)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_translation_file(translation_file_path, cache_file, pre_write_metadata, self._item_to_translated_line)

    def _write_translation_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        item_to_line: Callable[[CacheItem], str],
    ):
        if not cache_file.items:
            translation_file_path.touch()
            return

        # 处理所有项目
        lines = list(map(item_to_line, cache_file.items))

        translation_file_path.write_text("".join(lines), encoding=pre_write_metadata.encoding)

    def _item_to_bilingual_line(self, item: CacheItem):
        # 至少2个换行，让双语排版不那么紧凑，但用户说不需要，要原文排版
        line_break = "\n" * max(item.require_extra("line_break") + 1, 1)
        _indent = item.require_extra("sentence_indent")

        return (
            f"{item.source_text}\n"
            f"{item.translated_text}{line_break}"
        )

    def _item_to_translated_line(self, item: CacheItem):
        line_break = "\n" * (item.require_extra("line_break") + 1)

        # 原来有{item.require_extra("sentence_indent")}与translated_text的.lstrip()，现在不需要了
        return f"{item.translated_text}{line_break}"

    @classmethod
    def get_project_type(self):
        return ProjectType.TXT
