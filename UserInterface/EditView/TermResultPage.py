import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem, QAbstractItemView, QHeaderView
from qfluentwidgets import TableWidget
from Base.Base import Base

class TermResultPage(Base, QWidget):
    """
    用于显示术语提取结果的页面。
    """
    # 定义列索引常量
    COL_TERM = 0
    COL_TYPE = 1
    COL_CONTEXT = 2
    COL_FILE = 3

    def __init__(self, extraction_results: list, parent=None):
        super().__init__(parent)
        self.setObjectName('TermResultPage')
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 0, 0)
        self.layout.setSpacing(0)

        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)
        
        # 使用传入的结果填充表格
        self._populate_data(extraction_results)

    def _init_table(self):
        """初始化表格样式和表头"""
        self.headers = [self.tr("术语"), self.tr("类型"), self.tr("所在原文"), self.tr("来源文件")]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 设置表格为只读

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(self.COL_TERM, 180)
        self.table.setColumnWidth(self.COL_TYPE, 120)
        self.table.setColumnWidth(self.COL_CONTEXT, 400)
        self.table.setColumnWidth(self.COL_FILE, 180)

    def _populate_data(self, results: list):
        """用提取结果填充表格"""
        self.table.setRowCount(len(results))

        for row_idx, result in enumerate(results):
            term_item = QTableWidgetItem(result["term"])
            type_item = QTableWidgetItem(result["type"])
            context_item = QTableWidgetItem(result["context"])
            file_item = QTableWidgetItem(os.path.basename(result["file_path"]))

            self.table.setItem(row_idx, self.COL_TERM, term_item)
            self.table.setItem(row_idx, self.COL_TYPE, type_item)
            self.table.setItem(row_idx, self.COL_CONTEXT, context_item)
            self.table.setItem(row_idx, self.COL_FILE, file_item)
        
        self.table.resizeRowsToContents()