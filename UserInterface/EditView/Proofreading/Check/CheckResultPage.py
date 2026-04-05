from collections import defaultdict

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import Action, FluentIcon, RoundMenu, TableWidget

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from UserInterface.Widget.Toast import ToastMixin


class CheckResultPage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
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

        self.table.itemChanged.connect(self._on_item_changed)
        self.subscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)

    def closeEvent(self, event):
        try:
            self.unsubscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)
        except Exception:
            pass
        super().closeEvent(event)

    def _init_table(self):
        headers = [self.tra("行"), self.tra("错误"), self.tra("原文"), self.tra("检测文本")]
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
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 300)

    def _populate_data(self):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.results))

        for i, data in enumerate(self.results):
            row_id_raw = data.get("row_id", "")
            item_id = QTableWidgetItem()
            item_id.setText(str(row_id_raw))
            try:
                item_id.setData(Qt.DisplayRole, int(row_id_raw))
            except (ValueError, TypeError):
                pass

            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            meta_data = {
                "file_path": data.get("file_path"),
                "text_index": data.get("text_index"),
                "target_field": data.get("target_field"),
                "original_data_index": i,
            }
            item_id.setData(Qt.UserRole, meta_data)
            self.table.setItem(i, 0, item_id)

            item_type = QTableWidgetItem(data.get("error_type", ""))
            item_type.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(i, 1, item_type)

            item_src = QTableWidgetItem(data.get("source", ""))
            item_src.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(i, 2, item_src)

            item_check = QTableWidgetItem(data.get("check_text", ""))
            item_check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(i, 3, item_check)

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

        new_text = item.text()
        file_path = meta_data["file_path"]
        text_index = meta_data["text_index"]
        target_field = meta_data["target_field"]

        if file_path and text_index is not None:
            self.cache_manager.update_item_text(
                storage_path=file_path,
                text_index=text_index,
                field_name=target_field,
                new_text=new_text,
            )

            if "original_data_index" in meta_data:
                self.results[meta_data["original_data_index"]]["check_text"] = new_text

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

                if "original_data_index" in meta_data:
                    self.results[meta_data["original_data_index"]]["check_text"] = new_text
        finally:
            self.table.blockSignals(False)

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
        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.TABLE_TASK
        else:
            self.warning(self.tra("正在执行其他任务中！"))
            return

        selected_rows = sorted(list(set(index.row() for index in self.table.selectedIndexes())))
        if not selected_rows:
            return

        tasks_by_file = defaultdict(list)
        for row in selected_rows:
            id_item = self.table.item(row, 0)
            src_item = self.table.item(row, 2)
            if not id_item or not src_item:
                continue

            meta_data = id_item.data(Qt.UserRole)
            file_path = meta_data.get("file_path")
            text_index = meta_data.get("text_index")
            if file_path and text_index is not None:
                tasks_by_file[file_path].append(
                    {
                        "text_index": text_index,
                        "source_text": src_item.text(),
                    }
                )

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

        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()), reverse=True)
        for row in selected_rows:
            self.table.removeRow(row)

        self.table.setSortingEnabled(current_sorting)
