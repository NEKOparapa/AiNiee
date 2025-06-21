

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem, QAbstractItemView, 
                             QHeaderView)
from qfluentwidgets import (TableWidget, RoundMenu, Action, FluentIcon as FIF)

from Base.Base import Base

class BasicTablePage(Base, QWidget):
    # 定义列索引常量
    COL_NUM = 0
    COL_SOURCE = 1
    COL_TRANS = 2
    COL_POLISH = 3

    def __init__(self, file_path: str, file_items: list, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName('BasicTablePage')
        
        self.file_path = file_path
        self.cache_manager = cache_manager
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 0, 0)
        self.layout.setSpacing(0)

        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)
        
        self._populate_real_data(file_items)

        self.table.itemChanged.connect(self._on_item_changed)
        self.subscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)
        self.subscribe(Base.EVENT.TABLE_FORMAT, self._on_format_and_rebuild_table) 

    def _init_table(self):
        self.headers = ["行", "原文", "译文", "润文"]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(1, 400)
        self.table.setColumnWidth(2, 400)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def _populate_real_data(self, items: list):
        self.table.blockSignals(True)
        self.table.setRowCount(len(items))
        for row_idx, item_data in enumerate(items):
            num_item = QTableWidgetItem(str(row_idx + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
            num_item.setData(Qt.UserRole, item_data.text_index)
            self.table.setItem(row_idx, self.COL_NUM, num_item)

            source_item = QTableWidgetItem(item_data.source_text)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, self.COL_SOURCE, source_item)
            
            self.table.setItem(row_idx, self.COL_TRANS, QTableWidgetItem(item_data.translated_text))
            self.table.setItem(row_idx, self.COL_POLISH, QTableWidgetItem(item_data.polished_text or ''))
        
        self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()

        if col not in [self.COL_TRANS, self.COL_POLISH]:
            return
            
        text_index_item = self.table.item(row, self.COL_NUM)
        if not text_index_item:
            return 
        text_index = text_index_item.data(Qt.UserRole)
        new_text = item.text()
        
        field_name = 'translated_text' if col == self.COL_TRANS else 'polished_text'
        
        self.cache_manager.update_item_text(
            storage_path=self.file_path,
            text_index=text_index,
            field_name=field_name,
            new_text=new_text
        )

    def _show_context_menu(self, pos: QPoint):
        # ... (此方法内容不变，此处省略以节约篇幅)
        menu = RoundMenu(parent=self)
        has_selection = bool(self.table.selectionModel().selectedRows())
        if has_selection:
            menu.addAction(Action(FIF.EDIT, "翻译文本", triggered=self._translate_text))
            menu.addAction(Action(FIF.BRUSH, "润色文本", triggered=self._polish_text))
            menu.addAction(Action(FIF.BRUSH, "排序文本", triggered=self._format_text))
            menu.addSeparator()
            menu.addAction(Action(FIF.COPY, "禁止翻译", triggered=self._copy_source_to_translation))
            menu.addAction(Action(FIF.DELETE, "清空翻译", triggered=self._clear_translation))
            menu.addAction(Action(FIF.DELETE, "清空润色", triggered=self._clear_polishing))
            menu.addSeparator()
        row_count = self.table.rowCount()
        row_count_action = Action(FIF.LEAF, f"行数: {row_count}")
        row_count_action.setEnabled(False)
        menu.addAction(row_count_action)
        global_pos = self.table.mapToGlobal(pos)
        menu.exec(global_pos)

    # ... (所有其他方法 _on_table_update, _on_format_and_rebuild_table, _get_selected_rows_indices,等... 保持不变)
    # ... (此处省略以节约篇幅，请将 BasicTablePage 的所有方法都复制过来)
    def _on_table_update(self, event, data: dict):
        if data.get('file_path') != self.file_path: return
        target_column_index = data.get('target_column_index')
        updated_items = data.get('updated_items', {})
        if target_column_index is None or not updated_items:
            self.warning(f"表格更新数据不完整，操作中止。")
            return
        self.table.blockSignals(True)
        index_to_row_map = {self.table.item(row, self.COL_NUM).data(Qt.UserRole): row for row in range(self.table.rowCount()) if self.table.item(row, self.COL_NUM)}
        for text_index, new_text in updated_items.items():
            if text_index in index_to_row_map:
                row = index_to_row_map[text_index]
                self.table.setItem(row, target_column_index, QTableWidgetItem(new_text))
        self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def _on_format_and_rebuild_table(self, event, data: dict):
        if data.get('file_path') != self.file_path: return
        self.info(f"接收到文件 '{self.file_path}' 的排版更新，正在重建表格...")
        formatted_data = data.get('updated_items')
        selected_item_indices = data.get('selected_item_indices')
        if not formatted_data or selected_item_indices is None:
            self.error("排版更新失败：未收到有效的文本数据或原始选中项索引。")
            return
        updated_full_item_list = self.cache_manager.reformat_and_splice_cache(file_path=self.file_path, formatted_data=formatted_data, selected_item_indices=selected_item_indices)
        if updated_full_item_list is None:
            self.error("缓存拼接更新失败，表格更新中止。")
            return
        self._populate_real_data(updated_full_item_list)
        row_count_change = len(updated_full_item_list) - self.table.rowCount()
        self.info_toast("排版完成", f"表格已成功更新，行数变化: {row_count_change:+}")

    def _get_selected_rows_indices(self):
        return sorted(list(set(index.row() for index in self.table.selectedIndexes())))

    def _translate_text(self):
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows: return
        if Base.work_status == Base.STATUS.IDLE: Base.work_status = Base.STATUS.TABLE_TASK
        else: print("❌正在执行其他任务中！"); return
        items_to_translate = []
        for row in selected_rows:
            text_index_item = self.table.item(row, self.COL_NUM)
            source_text_item = self.table.item(row, self.COL_SOURCE)
            if text_index_item and source_text_item: items_to_translate.append({"text_index": text_index_item.data(Qt.UserRole), "source_text": source_text_item.text()})
        if not items_to_translate: return
        language_stats = self.cache_manager.project.get_file(self.file_path).language_stats
        self.emit(Base.EVENT.TABLE_TRANSLATE_START, {"file_path": self.file_path, "items_to_translate": items_to_translate, "language_stats": language_stats})
        self.info_toast("提示", f"已提交 {len(items_to_translate)} 行文本的翻译任务。")

    def _polish_text(self):
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows: return
        if Base.work_status == Base.STATUS.IDLE: Base.work_status = Base.STATUS.TABLE_TASK
        else: print("❌正在执行其他任务中！"); return
        items_to_polish = []
        for row in selected_rows:
            text_index_item = self.table.item(row, self.COL_NUM)
            source_text_item = self.table.item(row, self.COL_SOURCE)
            translation_text_item = self.table.item(row, self.COL_TRANS)
            if text_index_item and source_text_item: items_to_polish.append({"text_index": text_index_item.data(Qt.UserRole), "source_text": source_text_item.text(), "translation_text": translation_text_item.text()})
        if not items_to_polish: return
        self.emit(Base.EVENT.TABLE_POLISH_START, {"file_path": self.file_path, "items_to_polish": items_to_polish})
        self.info_toast("提示", f"已提交 {len(items_to_polish)} 行文本的润色任务。")

    def _format_text(self):
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows: return
        if Base.work_status == Base.STATUS.IDLE: Base.work_status = Base.STATUS.TABLE_TASK
        else: print("❌正在执行其他任务中！"); return
        items_to_format = []
        selected_item_indices = []
        for row in selected_rows:
            text_index_item = self.table.item(row, self.COL_NUM)
            source_text_item = self.table.item(row, self.COL_SOURCE)
            if text_index_item and source_text_item:
                text_index = text_index_item.data(Qt.UserRole)
                items_to_format.append({"text_index": text_index, "source_text": source_text_item.text()})
                selected_item_indices.append(text_index)
        if not items_to_format: return
        self.emit(Base.EVENT.TABLE_FORMAT_START, {"file_path": self.file_path, "items_to_format": items_to_format, "selected_item_indices": selected_item_indices})
        self.info_toast("提示", f"已提交 {len(items_to_format)} 行文本的排版任务。")

    def _copy_source_to_translation(self):
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows: return
        for row in selected_rows:
            source_item = self.table.item(row, self.COL_SOURCE)
            if source_item:
                source_text = source_item.text()
                trans_item = self.table.item(row, self.COL_TRANS)
                if trans_item: trans_item.setText(source_text)
                else: self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(source_text))
        self.info_toast("操作完成", f"已将 {len(selected_rows)} 行的原文复制到译文。")

    def _clear_translation(self):
        selected_rows = self._get_selected_rows_indices()
        for row in selected_rows:
            item = self.table.item(row, self.COL_TRANS)
            if item: item.setText("")
            else: self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(""))

    def _clear_polishing(self):
        selected_rows = self._get_selected_rows_indices()
        for row in selected_rows:
            item = self.table.item(row, self.COL_POLISH)
            if item: item.setText("")
            else: self.table.setItem(row, self.COL_POLISH, QTableWidgetItem(""))