import polib
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata,
)

class PoWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)
        try:
            import polib
        except ImportError:
            raise ImportError("`polib` is not installed. Please run 'pip install polib' to use PO file support.")

    @classmethod
    def get_project_type(cls):
        return ProjectType.PO

    def on_write_bilingual(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_po_file(translation_file_path, cache_file, pre_write_metadata)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_po_file(translation_file_path, cache_file, pre_write_metadata)

    def _write_po_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata
    ):
        po_file = polib.POFile()
        po_file.metadata = cache_file.extra.get('metadata', {})
        po_file.header = cache_file.extra.get('header', '')

        for item in cache_file.items:
            extra = item.extra
            entry = polib.POEntry(
                msgid=item.source_text,
                msgstr=item.final_text,
                msgctxt=extra.get('msgctxt'),
                msgid_plural=extra.get('msgid_plural', ''),
                comment=extra.get('comment', ''),
                tcomment=extra.get('tcomment', ''),
                occurrences=extra.get('occurrences', []),
                flags=extra.get('flags', []),
                previous_msgid=extra.get('previous_msgid'),
                previous_msgctxt=extra.get('previous_msgctxt'),
                linenum=extra.get('linenum')
            )
            po_file.append(entry)

        po_file.save(str(translation_file_path))