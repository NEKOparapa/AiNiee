
import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem, 
                             QAbstractItemView, QHeaderView)
from qfluentwidgets import TableWidget

class SearchResultPage(QWidget):
    # 定义列索引常量
    COL_FILE = 0
    COL_ROW = 1
    COL_SOURCE = 2
    COL_TRANS = 3
    COL_POLISH = 4

    def __init__(self, search_results: list, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName('SearchResultPage')
        
        self.cache_manager = cache_manager
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 0, 0)
        self.layout.setSpacing(0)

        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)
        
        self._populate_data(search_results)

        self.table.itemChanged.connect(self._on_item_changed)

    def _init_table(self):
        self.headers = ["文件", "行", "原文", "译文", "润文"]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 300)
        self.table.setColumnWidth(3, 300)

    def _populate_data(self, search_results: list):
        self.table.blockSignals(True)
        self.table.setRowCount(len(search_results))

        for row_idx, result_info in enumerate(search_results):
            file_path, original_row_num, item = result_info

            file_item = QTableWidgetItem(os.path.basename(file_path))
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, self.COL_FILE, file_item)

            row_num_item = QTableWidgetItem(str(original_row_num))
            row_num_item.setTextAlignment(Qt.AlignCenter)
            row_num_item.setFlags(row_num_item.flags() & ~Qt.ItemIsEditable)
            row_num_item.setData(Qt.UserRole, (file_path, item.text_index))
            self.table.setItem(row_idx, self.COL_ROW, row_num_item)

            source_item = QTableWidgetItem(item.source_text)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, self.COL_SOURCE, source_item)

            self.table.setItem(row_idx, self.COL_TRANS, QTableWidgetItem(item.translated_text))
            self.table.setItem(row_idx, self.COL_POLISH, QTableWidgetItem(item.polished_text or ''))
        
        self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()

        if col not in [self.COL_TRANS, self.COL_POLISH]:
            return

        ref_item = self.table.item(row, self.COL_ROW)
        if not ref_item:
            return
        
        file_path, text_index = ref_item.data(Qt.UserRole)
        new_text = item.text()

        field_name = 'translated_text' if col == self.COL_TRANS else 'polished_text'
        
        self.cache_manager.update_item_text(
            storage_path=file_path,
            text_index=text_index,
            field_name=field_name,
            new_text=new_text
        )