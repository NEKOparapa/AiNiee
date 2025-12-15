import csv
from pathlib import Path

from ModuleFolders.Infrastructure.Cache.CacheFile import CacheFile
from ModuleFolders.Infrastructure.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)

class CsvWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    @classmethod
    def get_project_type(cls):
        return "CSV"

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        if not source_file_path or not source_file_path.exists():
            print("Error: Source file not found for CSV reconstruction.")
            return

        # 1. 读取原始 CSV 数据到内存列表
        original_data = []
        source_encoding = cache_file.encoding or 'utf-8'
        
        try:
            with open(source_file_path, 'r', encoding=source_encoding, newline='') as f:
                reader = csv.reader(f)
                original_data = list(reader)
        except Exception as e:
            print(f"Error reading source CSV: {e}")
            return

        # 2. 将翻译填入对应位置
        for item in cache_file.items:
            row = item.get_extra("row")
            col = item.get_extra("col")
            translated_text = item.final_text
            
            if row is not None and col is not None and translated_text:
                # 确保索引不越界（防止源文件在读取后被修改）
                if row < len(original_data) and col < len(original_data[row]):
                    original_data[row][col] = translated_text

        # 3. 写入新的 CSV 文件
        try:
            # CSV输出通常建议用 utf-8-sig 以便 Excel 正确识别中文
            write_encoding = 'utf-8-sig' if pre_write_metadata.encoding == 'utf-8' else pre_write_metadata.encoding
            
            with open(translation_file_path, 'w', encoding=write_encoding, newline='') as f:
                writer = csv.writer(f)
                writer.writerows(original_data)
                
        except Exception as e:
            print(f"Error writing translated CSV: {e}")