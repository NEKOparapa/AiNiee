from functools import partial
from itertools import count
from pathlib import Path
from typing import Callable, Iterator

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig
)


class SrtWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_bilingual_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        _yield_bilingual_block = partial(self._yield_bilingual_block, counter=count(1))
        self._write_translation_file(translation_file_path, items, _yield_bilingual_block)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        self._write_translation_file(translation_file_path, items, self._yield_translated_block)

    def _write_translation_file(
        self, translation_file_path: Path, items: list[CacheItem],
        yield_block: Callable[[CacheItem], Iterator[list[str]]]
    ):
        output = []
        for item in items:
            if not item.get_source_text() or not item.get_translated_text():
                continue
            for block in yield_block(item):
                output.append("\n".join(block).strip())
        if output:
            translation_file_path.write_text("\n\n".join(output), encoding=self.translated_encoding)

    def _map_to_translated_item(self, item: CacheItem):
        block = [
            str(item.subtitle_number),
            item.subtitle_time,
            item.get_translated_text().strip(),
            "",
        ]
        return block

    def _yield_bilingual_block(self, item: CacheItem, counter: count):
        if self._strip_text(item.get_source_text()):
            number = next(counter)
            original_block = [
                str(number),
                item.subtitle_time,
                item.get_source_text().strip(),
                "",
            ]
            yield original_block
        if self._strip_text(item.get_translated_text()):
            number = next(counter)
            translated_block = self._map_to_translated_item(item)
            translated_block[0] = str(number)
            yield translated_block

    def _strip_text(self, text: str):
        return (text or "").strip()

    def _yield_translated_block(self, item: CacheItem):
        yield self._map_to_translated_item(item)

    @classmethod
    def get_project_type(self):
        return "Srt"
