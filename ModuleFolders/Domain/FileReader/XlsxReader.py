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


class XlsxReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig):
        super().__init__(input_config)

    @classmethod
    def get_project_type(cls):
        return ProjectType.XLSX

    @property
    def support_file(self):
        return "xlsx"

    def can_read_by_content(self, file_path: Path) -> bool:
        """检查文件内容是否为通用 xlsx 格式（不是 TPP 格式）"""
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True)
            sheet = wb.active
            
            # 读取第一行第一列和第二列的值
            cell_value1 = sheet.cell(row=1, column=1).value
            cell_value2 = sheet.cell(row=1, column=2).value
            
            wb.close()
            
            # 如果不是 TPP 格式（第一列不是 "Original Text" 或第二列不是 "Initial"），则认为是通用 xlsx 格式
            is_tpp = (isinstance(cell_value1, str) and cell_value1.strip() == "Original Text" and
                      isinstance(cell_value2, str) and cell_value2.strip() == "Initial")
            
            return not is_tpp
        except Exception:
            return False

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        items = []
        header = []
        
        try:
            # 1. 读取第一行作为表头
            if sheet.max_row > 0:
                for col in range(1, sheet.max_column + 1):
                    cell_value = sheet.cell(row=1, column=col).value
                    header.append(str(cell_value) if cell_value is not None else "")
            
            # 如果表头为空，返回 None
            if not header:
                return None
            
            # 2. 按列顺序读取剩余内容（从第二行开始）
            for row in range(2, sheet.max_row + 1):
                for col in range(1, sheet.max_column + 1):
                    cell_value = sheet.cell(row=row, column=col).value
                    
                    # 忽略空单元格，只记录有内容的
                    if cell_value is not None and str(cell_value).strip():
                        item = CacheItem(
                            source_text=str(cell_value),
                            translation_status=TranslationStatus.UNTRANSLATED,
                            extra={
                                "row": row - 2,  # 从0开始计数（表头不算）
                                "col": col - 1   # 从0开始计数
                            }
                        )
                        items.append(item)
                        
        except Exception as e:
            print(f"Error reading XLSX {file_path}: {e}")
            return None
        
        finally:
            wb.close()
        
        # 3. 如果除了表头没有内容则跳过该文件
        if not items:
            return None
        
        # 4. 将表头保存到 filecache 的 extra 中
        return CacheFile(items=items, extra={"header": header})
