import csv
from pathlib import Path

from ModuleFolders.Infrastructure.Cache.CacheFile import CacheFile
from ModuleFolders.Infrastructure.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Infrastructure.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)

class CsvReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return "Csv"

    @property
    def support_file(self):
        return "csv"

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        items = []
        encoding = pre_read_metadata.encoding
        
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                reader = csv.reader(f)
                for row_idx, row in enumerate(reader):
                    for col_idx, cell in enumerate(row):
                        if cell and cell.strip(): # 忽略空单元格
                            item = CacheItem(
                                source_text=cell,
                                translation_status=TranslationStatus.UNTRANSLATED,
                                extra={"row": row_idx, "col": col_idx} # 记录坐标以便写入
                            )
                            items.append(item)
        except Exception as e:
            print(f"Error reading CSV {file_path}: {e}")
            return None

        return CacheFile(items=items)