from pathlib import Path

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileAccessor.WolfXlsxAccessor import WolfXlsxAccessor
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata,
)


class WolfXlsxWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)
        self.file_accessor = WolfXlsxAccessor()

    @classmethod
    def get_project_type(cls):
        return ProjectType.WOLF_XLSX

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        if not source_file_path or not source_file_path.exists():
            print(f"Error writing WOLF XLSX: source file not found for {translation_file_path}")
            return

        translations = {}
        for item in cache_file.items:
            if item.translation_status not in (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED):
                continue

            row_index = item.get_extra("row_index")
            if row_index is None:
                continue

            translations[row_index] = item.final_text

        try:
            self.file_accessor.write_translations(source_file_path, translation_file_path, translations)
        except Exception as e:
            print(f"Error writing translated WOLF XLSX: {e}")
