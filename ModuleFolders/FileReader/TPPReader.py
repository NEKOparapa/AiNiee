from pathlib import Path

import openpyxl  # 需安装库pip install openpyxl

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    text_to_cache_item
)


class TPPReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return "Tpp"

    @property
    def support_file(self):
        return "xlsx"

    def read_source_file(self, file_path: Path, detected_encoding: str) -> list[CacheItem]:
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        items = []
        for row in range(2, sheet.max_row + 1):  # 从第二行开始读取，因为第一行是标识头，通常不用理会
            cell_value1 = sheet.cell(row=row, column=1).value  # 第N行第一列的值
            cell_value2 = sheet.cell(row=row, column=2).value  # 第N行第二列的值
            source_text = cell_value1  # 获取原文

            if cell_value1:
                # 第1列的值不为空，和第2列的值为空，是未翻译内容
                # 第1列的值不为空，和第2列的值不为空，是已经翻译内容
                if cell_value2 is not None:
                    translated_text = cell_value2
                    translation_status = CacheItem.STATUS.TRANSLATED
                else:
                    translated_text = ''
                    translation_status = CacheItem.STATUS.UNTRANSLATED
                item = text_to_cache_item(source_text, translated_text) # 存储文本对
                item.set_translation_status(translation_status) # 更新翻译状态
                item.set_row_index(row) # 存储行数信息
                items.append(item)
        return items
