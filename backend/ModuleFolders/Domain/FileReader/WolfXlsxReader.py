from pathlib import Path

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileAccessor.WolfXlsxAccessor import WolfXlsxAccessor
from ModuleFolders.Domain.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata,
)


class WolfXlsxReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)
        self.file_accessor = WolfXlsxAccessor()

    @classmethod
    def get_project_type(cls):
        return ProjectType.WOLF_XLSX

    @property
    def support_file(self):
        return "xlsx"

    def can_read_by_content(self, file_path: Path) -> bool:
        return self.file_accessor.is_wolf_workbook(file_path)

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        try:
            items = []
            file_extra = self.file_accessor.build_file_extra(file_path)

            for row_data in self.file_accessor.iter_rows(file_path):
                source_text = row_data["source_text"]
                info = row_data["info"]
                item_type = row_data["type"]
                if not self.file_accessor.should_translate(source_text, info, item_type):
                    continue

                translated_text = row_data["translated_text"]
                translation_status = (
                    TranslationStatus.TRANSLATED
                    if translated_text.strip()
                    else TranslationStatus.UNTRANSLATED
                )

                items.append(
                    CacheItem(
                        source_text=source_text,
                        translated_text=translated_text,
                        translation_status=translation_status,
                        extra={
                            "row_index": row_data["row_index"],
                            "code": row_data["code"],
                            "flag": row_data["flag"],
                            "type": row_data["type"],
                            "info": row_data["info"],
                            "notes": row_data["notes"],
                            "half_width_only": self.file_accessor.has_half_width_flag(row_data["flag"]),
                        },
                    )
                )

            if not items:
                return None

            return CacheFile(items=items, extra=file_extra)
        except Exception as e:
            print(f"Error reading WOLF XLSX {file_path}: {e}")
            return None
