from collections import defaultdict

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import Action, FluentIcon, RoundMenu, TableWidget

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from UserInterface.Widget.Toast import ToastMixin


class EditableIssueTablePage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
    def __init__(self, results: list, cache_manager=None, parent=None):
        super().__init__(parent)
        self.results = results
        self.cache_manager = cache_manager
        self.setObjectName("EditableIssueTablePage")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.table = TableWidget(self)
        self.layout.addWidget(self.table)

        self._init_table()
        self._populate_data()

        self.table.itemChanged.connect(self._on_item_changed)
        self.subscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)

    def closeEvent(self, event):
        try:
            self.unsubscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)
        except Exception:
            pass
        super().closeEvent(event)

    def _init_table(self):
        headers = [self.tra("行"), self.tra("错误"), self.tra("原文"), self.tra("译文")]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(False)

        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 320)

    def _populate_data(self):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.results))

        for row, data in enumerate(self.results):
            row_id_item = QTableWidgetItem(str(data.get("row_id", "")))
            row_id_item.setTextAlignment(Qt.AlignCenter)
            row_id_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            row_id_item.setData(
                Qt.UserRole,
                {
                    "file_path": data.get("file_path"),
                    "text_index": data.get("text_index"),
                    "target_field": data.get("target_field"),
                    "original_data_index": row,
                },
            )
            self.table.setItem(row, 0, row_id_item)

            error_item = QTableWidgetItem(data.get("error_type", ""))
            error_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, error_item)

            source_item = QTableWidgetItem(data.get("source", ""))
            source_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 2, source_item)

            check_item = QTableWidgetItem(data.get("check_text", ""))
            check_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(row, 3, check_item)

        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != 3:
            return

        id_item = self.table.item(item.row(), 0)
        if not id_item or not self.cache_manager:
            return

        meta_data = id_item.data(Qt.UserRole)
        if not meta_data:
            return

        file_path = meta_data.get("file_path")
        text_index = meta_data.get("text_index")
        target_field = meta_data.get("target_field")
        if file_path is None or text_index is None or not target_field:
            return

        new_text = item.text()
        self.cache_manager.update_item_text(
            storage_path=file_path,
            text_index=text_index,
            field_name=target_field,
            new_text=new_text,
        )

        original_index = meta_data.get("original_data_index")
        if original_index is not None and 0 <= original_index < len(self.results):
            self.results[original_index]["check_text"] = new_text

    def _on_table_update(self, event, data: dict):
        updated_file_path = data.get("file_path")
        if data.get("target_column_index") != 2:
            return

        updated_items = data.get("updated_items", {})
        if not updated_file_path or not updated_items:
            return

        translation_status = data.get("translation_status", TranslationStatus.TRANSLATED)

        self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                id_item = self.table.item(row, 0)
                if not id_item:
                    continue

                meta_data = id_item.data(Qt.UserRole)
                if not meta_data:
                    continue

                if meta_data.get("file_path") != updated_file_path:
                    continue
                if meta_data.get("target_field") != "translated_text":
                    continue

                text_index = meta_data.get("text_index")
                if text_index not in updated_items:
                    continue

                new_text = updated_items[text_index]
                check_text_item = self.table.item(row, 3)
                if check_text_item:
                    check_text_item.setText(new_text)

                self.cache_manager.update_generated_translation(
                    storage_path=updated_file_path,
                    text_index=text_index,
                    new_text=new_text,
                    translation_status=translation_status,
                )

                original_index = meta_data.get("original_data_index")
                if original_index is not None and 0 <= original_index < len(self.results):
                    self.results[original_index]["check_text"] = new_text
        finally:
            self.table.blockSignals(False)

        self.table.resizeRowsToContents()

    def _show_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self)
        has_selection = len(self.table.selectionModel().selectedRows()) > 0

        translate_action = Action(FluentIcon.EXPRESSIVE_INPUT_ENTRY, self.tra("翻译选中项"), self)
        translate_action.setEnabled(has_selection)
        translate_action.triggered.connect(self._translate_selected_rows)
        menu.addAction(translate_action)

        menu.addSeparator()

        delete_action = Action(FluentIcon.DELETE, self.tra("删除选中行"), self)
        delete_action.setEnabled(has_selection)
        delete_action.triggered.connect(self._delete_selected_rows)
        menu.addAction(delete_action)

        menu.exec(self.table.mapToGlobal(pos))

    def _translate_selected_rows(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not selected_rows:
            return

        if Base.work_status != Base.STATUS.IDLE:
            self.warning(self.tra("正在执行其他任务中！"))
            return

        tasks_by_file = defaultdict(list)

        for row in selected_rows:
            id_item = self.table.item(row, 0)
            source_item = self.table.item(row, 2)
            if not id_item or not source_item:
                continue

            meta_data = id_item.data(Qt.UserRole)
            file_path = meta_data.get("file_path")
            text_index = meta_data.get("text_index")
            if file_path and text_index is not None:
                tasks_by_file[file_path].append(
                    {
                        "text_index": text_index,
                        "source_text": source_item.text(),
                    }
                )

        if not tasks_by_file:
            return

        Base.work_status = Base.STATUS.TABLE_TASK
        count = 0
        for file_path, items_to_translate in tasks_by_file.items():
            if not items_to_translate:
                continue

            file_obj = self.cache_manager.project.get_file(file_path)
            language_stats = file_obj.language_stats if file_obj else None
            self.emit(
                Base.EVENT.TABLE_TRANSLATE_START,
                {
                    "file_path": file_path,
                    "items_to_translate": items_to_translate,
                    "language_stats": language_stats,
                },
            )
            count += len(items_to_translate)

        if count > 0:
            self.info_toast(self.tra("提示"), self.tra("已提交 {} 个条目的翻译任务。").format(count))

    def _delete_selected_rows(self):
        current_sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)

        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in selected_rows:
            self.table.removeRow(row)

        self.table.setSortingEnabled(current_sorting)
