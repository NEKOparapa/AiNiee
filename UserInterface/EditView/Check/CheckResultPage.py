from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem, 
                             QHeaderView, QAbstractItemView)
from qfluentwidgets import TableWidget, RoundMenu, Action, FluentIcon
from Base.Base import Base

class CheckResultPage(Base, QWidget):
    def __init__(self, results: list, cache_manager=None, parent=None):
        super().__init__(parent)
        self.results = results
        self.cache_manager = cache_manager
        self.setObjectName("CheckResultPage")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.table = TableWidget(self)
        self.layout.addWidget(self.table)
        
        self._init_table()
        self._populate_data()

        # 连接表格内容改变信号
        self.table.itemChanged.connect(self._on_item_changed)

    def _init_table(self):
        headers = [
            self.tra("行"),
            self.tra("错误"),
            self.tra("原文"),
            self.tra("检测文本")
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderRadius(8)
        
        # 设置选择模式
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # 列宽调整
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        
        # 允许点击表头排序，但不默认显示排序箭头
        header.setSortIndicatorShown(False)

        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 300)

    def _populate_data(self):
        self.table.blockSignals(True)
        
        self.table.setSortingEnabled(False) 
        self.table.setRowCount(len(self.results))
        
        for i, data in enumerate(self.results):
            # 尝试将行号转为int，以便正确排序 (1, 2, 10 而不是 1, 10, 2)
            row_id_raw = data.get("row_id", "")
            item_id = QTableWidgetItem()
            
            # 设置显示的文本
            item_id.setText(str(row_id_raw))
            
            # 尝试设置数值数据用于排序
            try:
                # 假设 row_id 是纯数字或可以转为数字
                sort_val = int(row_id_raw)
                item_id.setData(Qt.DisplayRole, sort_val) # 设置DisplayRole可以让TableWidget按数字排序
            except (ValueError, TypeError):
                # 如果转换失败（例如包含字母），就按默认字符串处理
                pass
                
            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable) 
            
            # 存储元数据
            meta_data = {
                "file_path": data.get("file_path"),
                "text_index": data.get("text_index"),
                "target_field": data.get("target_field"),
                "original_data_index": i
            }
            item_id.setData(Qt.UserRole, meta_data)
            self.table.setItem(i, 0, item_id)
            
            # 错误类型
            item_type = QTableWidgetItem(data.get("error_type", ""))
            item_type.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(i, 1, item_type)
            
            # 原文
            item_src = QTableWidgetItem(data.get("source", ""))
            item_src.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(i, 2, item_src)
            
            # 检测文本
            item_check = QTableWidgetItem(data.get("check_text", ""))
            item_check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(i, 3, item_check)
            
        self.table.resizeRowsToContents()
        
        # 填充完成后开启排序
        self.table.setSortingEnabled(True)
        
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != 3:
            return

        row = item.row()
        id_item = self.table.item(row, 0)
        meta_data = id_item.data(Qt.UserRole)
        
        if not meta_data or not self.cache_manager:
            return

        new_text = item.text()
        file_path = meta_data["file_path"]
        text_index = meta_data["text_index"]
        target_field = meta_data["target_field"]

        if file_path and text_index is not None:
            self.cache_manager.update_item_text(
                storage_path=file_path,
                text_index=text_index,
                field_name=target_field,
                new_text=new_text
            )
            
            if "original_data_index" in meta_data:
                self.results[meta_data["original_data_index"]]["check_text"] = new_text

    def _show_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self)
        selected_rows = self.table.selectionModel().selectedRows()
        
        delete_action = Action(FluentIcon.DELETE, self.tra("删除选中行"), self)
        delete_action.setEnabled(len(selected_rows) > 0)
        delete_action.triggered.connect(self._delete_selected_rows)
        menu.addAction(delete_action)
        
        menu.exec(self.table.mapToGlobal(pos))

    def _delete_selected_rows(self):
        # 删除时需要先关闭排序，否则删除过程中索引可能会变动导致异常
        current_sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()), reverse=True)
        
        if selected_rows:
            for row in selected_rows:
                self.table.removeRow(row)
        
        # 恢复排序状态
        self.table.setSortingEnabled(current_sorting)