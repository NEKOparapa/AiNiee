from pathlib import Path

import openpyxl  # 需安装库pip install openpyxl
import re

from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class XlsxWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.XLSX

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        if not source_file_path or not source_file_path.exists():
            print(f"Error: source file not found for {translation_file_path.name}")
            return

        try:
            # 以源文件为模板写回：保留其余工作表、样式、列宽、公式和数值类型
            # （旧实现重建单表工作簿，会丢失除活动表外的一切内容并把数字/日期变成文本）
            wb = openpyxl.load_workbook(source_file_path)
            ws = wb.active

            # 只取已翻译条目：未翻译单元格完全不改动
            translated_map = {
                (item.get_extra("row"), item.get_extra("col")): item.final_text
                for item in cache_file.items
                if item.translation_status in (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED)
                and item.final_text and item.final_text.strip()
            }

            # row 从0开始计数（表头不算），写入时需要 +2（+1因为从0开始，+1因为表头占一行）；col +1
            for (r, c), new_text in translated_map.items():
                row_index = r + 2
                col_index = c + 1
                cell = ws.cell(row=row_index, column=col_index)

                # 只替换字符串单元格：数值/日期/公式单元格保持原值与类型，
                # 避免"数字存成文本"与公式被译文覆盖
                if not isinstance(cell.value, str):
                    continue

                # 过滤非法控制字符（openpyxl会直接抛错），直接赋值由openpyxl负责XML转义，
                # 不再调用escape()双重复转义（否则&会显示为&amp;）
                filtered_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", new_text)
                try:
                    cell.value = filtered_text
                except Exception as cell_error:
                    print(f"Error writing cell ({row_index},{col_index}): {cell_error}")

            # 保存工作簿
            wb.save(translation_file_path)

        except Exception as e:
            print(f"Error writing translated XLSX: {e}")
