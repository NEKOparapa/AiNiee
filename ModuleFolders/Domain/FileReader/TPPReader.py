from pathlib import Path

import openpyxl  # 需安装库pip install openpyxl

from ModuleFolders.Infrastructure.Cache.CacheFile import CacheFile
from ModuleFolders.Infrastructure.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Infrastructure.Cache.CacheProject import ProjectType
from ModuleFolders.Domain.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class TPPReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.TPP

    @property
    def support_file(self):
        return "xlsx"

    def can_read_by_content(self, file_path: Path) -> bool:
        """检查文件内容是否符合 TPP 格式：第一行第一列是 'Original Text'，第二列是 'Initial'"""
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True)
            sheet = wb.active
            
            # 读取第一行第一列和第二列的值
            cell_value1 = sheet.cell(row=1, column=1).value
            cell_value2 = sheet.cell(row=1, column=2).value
            
            wb.close()
            
            # 判断是否为 TPP 格式
            # 第一列应该是 "Original Text"或者"原文"，第二列应该是 "Initial"或者"译文"
            return (isinstance(cell_value1, str) and (cell_value1.strip() == "Original Text" or cell_value1.strip() == "原文") and
                    isinstance(cell_value2, str) and (cell_value2.strip() == "Initial" or cell_value2.strip() == "译文"))
        except Exception:
            return False

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        items = []
        for row in range(2, sheet.max_row + 1):  # 从第二行开始读取，因为第一行是标识头，通常不用理会
            cell_value1 = sheet.cell(row=row, column=1).value  # 第N行第一列的值
            cell_value2 = sheet.cell(row=row, column=2).value  # 第N行第二列的值
            source_text = str(cell_value1) if cell_value1 is not None else ""  # 获取原文

            if cell_value1:
                # 第1列的值不为空，和第2列的值为空，是未翻译内容
                # 第1列的值不为空，和第2列的值不为空，是已经翻译内容
                if cell_value2 is not None:
                    translated_text = cell_value2
                    translation_status = TranslationStatus.TRANSLATED
                else:
                    translated_text = ''
                    translation_status = TranslationStatus.UNTRANSLATED

                item = CacheItem(
                    source_text=source_text,
                    translated_text=translated_text,
                    translation_status=translation_status,
                    extra={"row_index": row},
                )
                items.append(item)
        return CacheFile(items=items)
