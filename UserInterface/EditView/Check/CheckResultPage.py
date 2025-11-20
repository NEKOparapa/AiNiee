from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem, 
                             QHeaderView, QAbstractItemView)
from qfluentwidgets import TableWidget, RoundMenu, Action, FluentIcon
from Base.Base import Base

class CheckResultPage(Base, QWidget):
    def __init__(self, results: list, cache_manager=None, parent=None):
        super().__init__(parent)
        self.results = results
        self.cache_manager = cache_manager  # 接收 cache_manager 以便更新数据
        self.setObjectName("CheckResultPage")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.table = TableWidget(self)
        self.layout.addWidget(self.table)
        
        self._init_table()
        self._populate_data()

        # 连接表格内容改变信号，用于实时更新
        self.table.itemChanged.connect(self._on_item_changed)

    def _init_table(self):
        # 列定义: 行id，错误类型，原文，检测文本
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
        
        # 设置选择模式，支持右键菜单
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # 列宽调整
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        
        self.table.setColumnWidth(0, 150) # 行ID
        self.table.setColumnWidth(1, 150) # 错误类型
        self.table.setColumnWidth(2, 300) # 原文

    def _populate_data(self):
        self.table.blockSignals(True) # 暂停信号防止触发更新
        self.table.setRowCount(len(self.results))
        
        for i, data in enumerate(self.results):
            # 行ID
            item_id = QTableWidgetItem(data.get("row_id", ""))
            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable) 
            
            # 将元数据存储在第一列的 UserRole 中，供更新使用
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
            
            # 检测文本 - 允许编辑
            item_check = QTableWidgetItem(data.get("check_text", ""))
            item_check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(i, 3, item_check)
            
        self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        """当用户编辑检测文本列时触发"""
        if item.column() != 3: # 只处理检测文本列
            return

        row = item.row()
        # 获取对应的元数据（存储在第0列）
        id_item = self.table.item(row, 0)
        meta_data = id_item.data(Qt.UserRole)
        
        if not meta_data or not self.cache_manager:
            return

        new_text = item.text()
        file_path = meta_data["file_path"]
        text_index = meta_data["text_index"]
        target_field = meta_data["target_field"]

        # 更新后端缓存
        if file_path and text_index is not None:
            self.cache_manager.update_item_text(
                storage_path=file_path,
                text_index=text_index,
                field_name=target_field,
                new_text=new_text
            )
            
            # 同步更新内存中 results 列表的数据
            if "original_data_index" in meta_data:
                self.results[meta_data["original_data_index"]]["check_text"] = new_text

    def _show_context_menu(self, pos: QPoint):
        """显示右键菜单"""
        menu = RoundMenu(parent=self)
        
        selected_rows = self.table.selectionModel().selectedRows()
        
        delete_action = Action(FluentIcon.DELETE, self.tra("删除选中行"), self)
        delete_action.setEnabled(len(selected_rows) > 0)
        delete_action.triggered.connect(self._delete_selected_rows)
        menu.addAction(delete_action)
        
        menu.exec(self.table.mapToGlobal(pos))

    def _delete_selected_rows(self):
        """删除选中行"""
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()), reverse=True)
        
        if not selected_rows:
            return

        # 从表格中移除行
        for row in selected_rows:
            self.table.removeRow(row)