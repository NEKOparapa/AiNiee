from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QTableWidgetItem, QWidget, QVBoxLayout
from qfluentwidgets import Action, FluentIcon as FIF, RoundMenu

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from UserInterface.Widget.AutoHeightTableWidget import AutoHeightTableWidget
from UserInterface.Widget.Toast import ToastMixin


class BasicTablePage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
    COL_NUM = 0
    COL_SOURCE = 1
    COL_TRANS = 2

    def closeEvent(self, event):
        try:
            self.unsubscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)
        except Exception:
            pass
        super().closeEvent(event)

    def __init__(self, file_path: str, file_items: list, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("BasicTablePage")

        self._item_changed_handler_enabled = True
        self.file_path = file_path
        self.cache_manager = cache_manager

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 0, 0)
        self.layout.setSpacing(0)

        self.table = AutoHeightTableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)

        self._populate_real_data(file_items)

        self.table.itemChanged.connect(self._on_item_changed)
        self.subscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)

    def _init_table(self):
        self.headers = [self.tra("行"), self.tra("原文"), self.tra("译文")]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setAutoHeightColumns((self.COL_SOURCE, self.COL_TRANS))
        self.table.setMultilineEditColumns((self.COL_TRANS,))

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self.table.setColumnWidth(self.COL_NUM, 60)
        self.table.setColumnWidth(self.COL_SOURCE, 400)
        self.table.setColumnWidth(self.COL_TRANS, 400)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def _populate_real_data(self, items: list):
        self._item_changed_handler_enabled = False
        try:
            highlight_brush = QBrush(QColor(144, 238, 144, 100))

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

                trans_item = QTableWidgetItem(item_data.translated_text)
                self.table.setItem(row_idx, self.COL_TRANS, trans_item)

                if item_data.extra and item_data.extra.get("language_mismatch_translation", False):
                    trans_item.setBackground(highlight_brush)
            self.table.resizeRowsToContents()
        finally:
            self._item_changed_handler_enabled = True

    def _on_item_changed(self, item: QTableWidgetItem):
        if not self._item_changed_handler_enabled:
            return

        row = item.row()
        col = item.column()
        if col != self.COL_TRANS:
            return

        text_index_item = self.table.item(row, self.COL_NUM)
        if not text_index_item:
            return

        text_index = text_index_item.data(Qt.UserRole)
        new_text = item.text()

        self.cache_manager.update_item_text(
            storage_path=self.file_path,
            text_index=text_index,
            field_name="translated_text",
            new_text=new_text,
        )
        self.table.resizeRowToContentsSafe(row)

    def _show_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self)
        has_selection = bool(self.table.selectionModel().selectedRows())
        if has_selection:
            menu.addAction(Action(FIF.EXPRESSIVE_INPUT_ENTRY, self.tra("翻译文本"), triggered=self._translate_text))
            menu.addAction(Action(FIF.BRUSH, self.tra("润色文本"), triggered=self._polish_text))
            menu.addSeparator()
            menu.addAction(Action(FIF.DELETE, self.tra("清空翻译"), triggered=self._clear_translation))
            menu.addSeparator()

        row_count_action = Action(FIF.LEAF, self.tra("行数: {}").format(self.table.rowCount()))
        row_count_action.setEnabled(False)
        menu.addAction(row_count_action)
        menu.exec(self.table.mapToGlobal(pos))

    def _on_table_update(self, event, data: dict):
        if data.get("file_path") != self.file_path:
            return

        if data.get("target_column_index") != self.COL_TRANS:
            return

        updated_items = data.get("updated_items", {})
        if not updated_items:
            return

        translation_status = data.get("translation_status", TranslationStatus.TRANSLATED)

        self._item_changed_handler_enabled = False
        try:
            index_to_row_map = {
                self.table.item(row, self.COL_NUM).data(Qt.UserRole): row
                for row in range(self.table.rowCount())
                if self.table.item(row, self.COL_NUM)
            }

            for text_index, new_text in updated_items.items():
                row = index_to_row_map.get(text_index)
                if row is None:
                    continue

                item = self.table.item(row, self.COL_TRANS)
                if item:
                    item.setText(new_text)
                else:
                    self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(new_text))

                self.cache_manager.update_generated_translation(
                    storage_path=self.file_path,
                    text_index=text_index,
                    new_text=new_text,
                    translation_status=translation_status,
                )

            self.table.scheduleResizeRowsToContents()
        finally:
            self._item_changed_handler_enabled = True

    def _get_selected_rows_indices(self):
        return sorted(list(set(index.row() for index in self.table.selectedIndexes())))

    def _translate_text(self):
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return

        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.TABLE_TASK
        else:
            print("❌正在执行其他任务中！")
            return

        items_to_translate = []
        for row in selected_rows:
            text_index_item = self.table.item(row, self.COL_NUM)
            source_text_item = self.table.item(row, self.COL_SOURCE)
            if text_index_item and source_text_item:
                items_to_translate.append(
                    {
                        "text_index": text_index_item.data(Qt.UserRole),
                        "source_text": source_text_item.text(),
                    }
                )

        if not items_to_translate:
            return

        language_stats = self.cache_manager.project.get_file(self.file_path).language_stats
        self.emit(
            Base.EVENT.TABLE_TRANSLATE_START,
            {
                "file_path": self.file_path,
                "items_to_translate": items_to_translate,
                "language_stats": language_stats,
            },
        )
        self.info_toast(self.tra("提示"), self.tra("已提交 {} 行文本的翻译任务。").format(len(items_to_translate)))

    def _polish_text(self):
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return

        items_to_polish = []
        for row in selected_rows:
            text_index_item = self.table.item(row, self.COL_NUM)
            source_text_item = self.table.item(row, self.COL_SOURCE)
            translation_text_item = self.table.item(row, self.COL_TRANS)
            translation_text = translation_text_item.text().strip() if translation_text_item else ""
            if text_index_item and source_text_item and translation_text:
                items_to_polish.append(
                    {
                        "text_index": text_index_item.data(Qt.UserRole),
                        "source_text": source_text_item.text(),
                        "translation_text": translation_text,
                    }
                )

        if not items_to_polish:
            self.warning_toast(self.tra("提示"), self.tra("润色前请先确保译文列有内容。"))
            return

        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.TABLE_TASK
        else:
            print("❌正在执行其他任务中！")
            return

        self.emit(
            Base.EVENT.TABLE_POLISH_START,
            {
                "file_path": self.file_path,
                "items_to_polish": items_to_polish,
            },
        )
        self.info_toast(self.tra("提示"), self.tra("已提交 {} 行文本的润色任务。").format(len(items_to_polish)))

    def _clear_translation(self):
        selected_rows = self._get_selected_rows_indices()
        for row in selected_rows:
            item = self.table.item(row, self.COL_TRANS)
            if item:
                item.setText("")
            else:
                self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(""))
