import csv
from pathlib import Path

from ModuleFolders.Infrastructure.Cache.CacheFile import CacheFile
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
        return "Csv"

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        # 1. 从 extra 中获取表头
        header = cache_file.get_extra("header")
        if not header:
            print(f"Error: Header not found in cache for {translation_file_path.name}")
            return

        # 2. 构建数据映射以便快速查找: (row, col) -> final_text
        # 使用 final_text 确保获取的是 润色后 > 翻译后 > 原文
        data_map = {
            (item.get_extra("row"), item.get_extra("col")): item.final_text 
            for item in cache_file.items
        }

        # 3. 计算最大行数
        # 如果没有 items (理论上 reader 会跳过，但为了安全)，最大行数设为0
        max_row = 0
        if data_map:
            max_row = max(r for r, c in data_map.keys())

        # 列数由表头决定
        num_cols = len(header)

        # 4. 直接创建新文件并写入
        try:
            # 强制使用 utf-8-sig 以便 Excel 正确识别中文，或者遵循 metadata
            write_encoding = 'utf-8-sig' if pre_write_metadata.encoding == 'utf-8' else pre_write_metadata.encoding
            
            with open(translation_file_path, 'w', encoding=write_encoding, newline='') as f:
                writer = csv.writer(f)
                
                # 写入表头
                writer.writerow(header)
                
                # 写入内容：从第1行开始重建数据（第0行是表头）
                for r in range(1, max_row + 1):
                    row_data = []
                    for c in range(num_cols):
                        # 获取翻译内容，如果源文件该处为空（reader跳过了），则填入空字符串
                        text = data_map.get((r, c), "")
                        row_data.append(text)
                    writer.writerow(row_data)
                    
        except Exception as e:
            print(f"Error writing translated CSV: {e}")