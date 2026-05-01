from math import ceil

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QTableWidgetItem,
    QWidget,
    QVBoxLayout,
)
from qfluentwidgets import (
    Action,
    FluentIcon as FIF,
    HorizontalPipsPager,
    PipsScrollButtonDisplayMode,
    RoundMenu,
    StrongBodyLabel,
    setFont,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from UserInterface.Widget.AutoHeightTableWidget import AutoHeightTableWidget
from UserInterface.Widget.Toast import ToastMixin


class BasicTablePage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
    PAGE_SIZE = 3000
    COL_NUM = 0
    COL_SOURCE = 1
    COL_TRANS = 2
    UPDATE_EVENT = Base.EVENT.TABLE_BASIC_UPDATE
    DONE_EVENT = Base.EVENT.TABLE_BASIC_DONE

    def closeEvent(self, event):
        try:
            self.unsubscribe(self.UPDATE_EVENT, self._on_table_update)
        except Exception:
            pass
        try:
            self.unsubscribe(self.DONE_EVENT, self._on_task_done)
        except Exception:
            pass
        super().closeEvent(event)

    def __init__(self, file_path: str, file_items: list, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("BasicTablePage")

        self._item_changed_handler_enabled = True
        self.file_path = file_path
        self.cache_manager = cache_manager
        self._all_items = file_items or []
        self._items_by_text_index = {item.text_index: item for item in self._all_items}
        self._current_page_index = 0
        self._page_count = ceil(len(self._all_items) / self.PAGE_SIZE) if self._all_items else 0

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 0, 0)
        self.layout.setSpacing(0)

        self.table = AutoHeightTableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table, 1)

        self._init_pager()
        self.layout.addWidget(self.pager_container)

        self._update_pager()
        self._populate_real_data(self._current_page_index)

        self.table.itemChanged.connect(self._on_item_changed)
        self.pager.currentIndexChanged.connect(self._on_page_changed)
        self.subscribe(self.UPDATE_EVENT, self._on_table_update)
        self.subscribe(self.DONE_EVENT, self._on_task_done)

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

    def _init_pager(self):
        self.pager_container = QWidget(self)
        pager_layout = QHBoxLayout(self.pager_container)
        pager_layout.setContentsMargins(0, 8, 0, 8)
        pager_layout.setSpacing(0)

        self.pager = HorizontalPipsPager(self.pager_container)
        self.pager.setNextButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)
        self.pager.setPreviousButtonDisplayMode(PipsScrollButtonDisplayMode.ALWAYS)
        self.page_info_label = StrongBodyLabel("", self.pager_container)
        setFont(self.page_info_label, 12)
        self.page_info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.page_info_label.setFixedHeight(14)

        pager_layout.addStretch(1)
        pager_layout.addWidget(self.pager)
        pager_layout.addSpacing(12)
        pager_layout.addWidget(self.page_info_label)
        pager_layout.addStretch(1)

    def _update_pager(self):
        visible_number = min(8, max(1, self._page_count))
        self.pager.setVisibleNumber(visible_number)
        self.pager.setPageNumber(self._page_count)
        if self._page_count > 0:
            self.pager.setCurrentIndex(min(self._current_page_index, self._page_count - 1))

        self._update_page_info_label()
        self.pager_container.setVisible(self._page_count > 1)

    def _get_page_range(self, page_index: int):
        if page_index < 0 or self._page_count == 0:
            return 0, 0

        start = page_index * self.PAGE_SIZE
        end = min(start + self.PAGE_SIZE, len(self._all_items))
        return start, end

    def _get_page_items(self, page_index: int):
        start, end = self._get_page_range(page_index)
        return self._all_items[start:end], start

    def _populate_real_data(self, page_index: int):
        page_items, start_index = self._get_page_items(page_index)
        self._item_changed_handler_enabled = False
        try:
            highlight_brush = QBrush(QColor(144, 238, 144, 100))

            self.table.clearContents()
            self.table.setRowCount(len(page_items))
            for row_idx, item_data in enumerate(page_items):
                num_item = QTableWidgetItem(str(start_index + row_idx + 1))
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
            self.table.scheduleResizeRowsToContents()
        finally:
            self._item_changed_handler_enabled = True

    def _on_page_changed(self, page_index: int):
        if page_index == self._current_page_index:
            return

        if not 0 <= page_index < self._page_count:
            return

        self._current_page_index = page_index
        self._update_page_info_label()
        self._populate_real_data(page_index)

    def _get_current_page_number(self):
        if self._page_count == 0:
            return 0
        return self._current_page_index + 1

    def _update_page_info_label(self):
        self.page_info_label.setText(f"{self._get_current_page_number()}/{max(1, self._page_count)}")

    def _sync_local_item(self, text_index: int, new_text: str, translation_status: int | None = None):
        item = self._items_by_text_index.get(text_index)
        if item is None:
            return

        item.translated_text = new_text
        if not new_text or not new_text.strip():
            item.translation_status = TranslationStatus.UNTRANSLATED
        elif translation_status is not None:
            item.translation_status = translation_status
        else:
            item.translation_status = TranslationStatus.TRANSLATED

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
        self._sync_local_item(text_index, new_text)
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

        row_count_action = Action(
            FIF.LEAF,
            self.tra("总行数: {}").format(len(self._all_items)),
        )
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

        for text_index, new_text in updated_items.items():
            self.cache_manager.update_generated_translation(
                storage_path=self.file_path,
                text_index=text_index,
                new_text=new_text,
                translation_status=translation_status,
            )
            self._sync_local_item(text_index, new_text, translation_status)

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

            self.table.scheduleResizeRowsToContents()
        finally:
            self._item_changed_handler_enabled = True

    def _on_task_done(self, event, data: dict):
        if data.get("file_path") != self.file_path or not self.isVisible():
            return

        operation = data.get("operation")
        status = data.get("status")
        updated_item_count = data.get("updated_item_count", 0)

        if operation == "translate":
            if status == "success":
                self.success_toast(self.tra("完成"), self.tra("表格翻译任务完成，已更新 {} 行。").format(updated_item_count))
            elif status == "empty":
                self.warning_toast(self.tra("提示"), self.tra("表格翻译任务结束，但没有可回写的结果。"))
        elif operation == "polish":
            if status == "success":
                self.success_toast(self.tra("完成"), self.tra("表格润色任务完成，已更新 {} 行。").format(updated_item_count))
            elif status == "empty":
                self.warning_toast(self.tra("提示"), self.tra("表格润色任务结束，但没有可回写的结果。"))

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
            self.warning_toast(self.tra("提示"), self.tra("正在执行其他任务中！"))
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
                "update_event": self.UPDATE_EVENT,
                "done_event": self.DONE_EVENT,
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
            self.warning_toast(self.tra("提示"), self.tra("正在执行其他任务中！"))
            return

        self.emit(
            Base.EVENT.TABLE_POLISH_START,
            {
                "file_path": self.file_path,
                "items_to_polish": items_to_polish,
                "update_event": self.UPDATE_EVENT,
                "done_event": self.DONE_EVENT,
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
