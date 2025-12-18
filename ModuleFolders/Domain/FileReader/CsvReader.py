import csv
from pathlib import Path

from ModuleFolders.Infrastructure.Cache.CacheFile import CacheFile
from ModuleFolders.Infrastructure.Cache.CacheItem import CacheItem, TranslationStatus
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
        header = []
        
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                reader = csv.reader(f)
                
                # 1. 尝试读取第一行作为表头
                try:
                    header = next(reader)
                except StopIteration:
                    # 文件为空
                    return None

                # 2. 按列从左往右读取剩余内容
                # start=1 因为第0行是表头
                for row_idx, row in enumerate(reader, start=1):
                    for col_idx, cell in enumerate(row):
                        # 忽略空单元格，只记录有内容的
                        if cell and cell.strip(): 
                            item = CacheItem(
                                source_text=cell,
                                translation_status=TranslationStatus.UNTRANSLATED,
                                extra={"row": row_idx, "col": col_idx} # 记录坐标
                            )
                            items.append(item)
                            
        except Exception as e:
            print(f"Error reading CSV {file_path}: {e}")
            return None

        # 3. 如果除了行号(表头)没有内容则跳过该文件
        if not items:
            return None

        # 4. 将表头保存到 filecache 的 extra 中
        return CacheFile(items=items, extra={"header": header})