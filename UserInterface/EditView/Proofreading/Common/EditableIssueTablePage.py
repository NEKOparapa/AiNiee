import os
from collections import defaultdict

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import Action, FluentIcon, PrimaryPushButton, RoundMenu, StrongBodyLabel

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from UserInterface.Widget.AutoHeightTableWidget import AutoHeightTableWidget
from UserInterface.Widget.Toast import ToastMixin


class EditableIssueTablePage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
    COL_FILE = 0
    COL_ROW = 1
    COL_ERROR = 2
    COL_SOURCE = 3
    COL_TRANS = 4

    def __init__(
        self,
        results: list,
        cache_manager=None,
        parent=None,
        update_event: int = Base.EVENT.TABLE_UPDATE,
        done_event: int | None = None,
    ):
        super().__init__(parent)
        self.results = results
        self.cache_manager = cache_manager
        self.update_event = update_event
        self.done_event = done_event
        self.setObjectName("EditableIssueTablePage")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 8)
        self.layout.setSpacing(6)

        self._init_action_bar()

        self.table = AutoHeightTableWidget(self)
        self.layout.addWidget(self.table)

        self._init_table()
        self._populate_data()

        self.table.itemChanged.connect(self._on_item_changed)
        self.subscribe(self.update_event, self._on_table_update)
        if self.done_event is not None:
            self.subscribe(self.done_event, self._on_task_done)

    def closeEvent(self, event):
        try:
            self.unsubscribe(self.update_event, self._on_table_update)
        except Exception:
            pass
        if self.done_event is not None:
            try:
                self.unsubscribe(self.done_event, self._on_task_done)
            except Exception:
                pass
        super().closeEvent(event)

    def _init_action_bar(self):
        action_bar = QWidget(self)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(0, 0, 0, 4)
        action_layout.setSpacing(8)

        self.result_table_label = StrongBodyLabel(self.tra("检查结果表"), action_bar)
        action_layout.addWidget(self.result_table_label)
        action_layout.addStretch(1)

        self.auto_proofread_button = PrimaryPushButton(self.tra("AI自动校对"), action_bar)
        self.auto_proofread_button.setEnabled(bool(self.results))
        self.auto_proofread_button.clicked.connect(self._proofread_all_rows)
        action_layout.addWidget(self.auto_proofread_button)

        self.layout.addWidget(action_bar)

    def _init_table(self):
        headers = [
            self.tra("文件"),
            self.tra("行"),
            self.tra("错误"),
            self.tra("原文"),
            self.tra("译文"),
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setAutoHeightColumns((self.COL_SOURCE, self.COL_TRANS))
        self.table.setMultilineEditColumns((self.COL_TRANS,))
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(False)

        self.table.setColumnWidth(self.COL_FILE, 180)
        self.table.setColumnWidth(self.COL_ROW, 70)
        self.table.setColumnWidth(self.COL_ERROR, 170)
        self.table.setColumnWidth(self.COL_SOURCE, 320)

    def _build_row_meta(self, data: dict, original_data_index: int) -> dict:
        return {
            "file_path": data.get("file_path"),
            "text_index": data.get("text_index"),
            "target_field": data.get("target_field"),
            "original_data_index": original_data_index,
        }

    def _populate_data(self):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.results))

        for row, data in enumerate(self.results):
            file_path = data.get("file_path", "")
            text_index = data.get("text_index")
            row_number = data.get("row_number", (text_index + 1) if text_index is not None else "")

            file_item = QTableWidgetItem(os.path.basename(file_path) if file_path else "")
            file_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, self.COL_FILE, file_item)

            row_item = QTableWidgetItem(str(row_number))
            row_item.setTextAlignment(Qt.AlignCenter)
            row_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            row_item.setData(Qt.UserRole, self._build_row_meta(data, row))
            self.table.setItem(row, self.COL_ROW, row_item)

            error_item = QTableWidgetItem(data.get("error_type", ""))
            error_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, self.COL_ERROR, error_item)

            source_item = QTableWidgetItem(data.get("source", ""))
            source_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, self.COL_SOURCE, source_item)

            check_item = QTableWidgetItem(data.get("check_text", ""))
            check_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(row, self.COL_TRANS, check_item)

        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

    def _get_row_meta(self, row: int) -> dict | None:
        row_item = self.table.item(row, self.COL_ROW)
        if not row_item:
            return None
        return row_item.data(Qt.UserRole)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != self.COL_TRANS:
            return

        if not self.cache_manager:
            return

        meta_data = self._get_row_meta(item.row())
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
        self.table.resizeRowToContentsSafe(item.row())

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
                meta_data = self._get_row_meta(row)
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
                check_text_item = self.table.item(row, self.COL_TRANS)
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

        self.table.scheduleResizeRowsToContents()

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

    def _proofread_all_rows(self):
        if Base.work_status != Base.STATUS.IDLE:
            self.warning_toast(self.tra("提示"), self.tra("当前有其他任务正在执行，请稍后再试。"))
            return

        tasks_by_file = defaultdict(list)

        for row in range(self.table.rowCount()):
            meta_data = self._get_row_meta(row)
            error_item = self.table.item(row, self.COL_ERROR)
            source_item = self.table.item(row, self.COL_SOURCE)
            check_item = self.table.item(row, self.COL_TRANS)
            if not meta_data or not source_item:
                continue

            file_path = meta_data.get("file_path")
            text_index = meta_data.get("text_index")
            if not file_path or text_index is None:
                continue

            tasks_by_file[file_path].append(
                {
                    "text_index": text_index,
                    "source_text": source_item.text(),
                    "translation_text": check_item.text() if check_item else "",
                    "error_type": error_item.text() if error_item else "",
                }
            )

        if not tasks_by_file:
            self.warning_toast(self.tra("提示"), self.tra("当前没有可执行 AI 校对的条目。"))
            return

        proofread_jobs = []
        count = 0
        for file_path, items_to_proofread in tasks_by_file.items():
            if not items_to_proofread:
                continue

            proofread_jobs.append(
                {
                    "file_path": file_path,
                    "items_to_proofread": items_to_proofread,
                }
            )
            count += len(items_to_proofread)

        if count > 0:
            self.emit(
                Base.EVENT.TABLE_PROOFREAD_START,
                {
                    "proofread_jobs": proofread_jobs,
                    "update_event": self.update_event,
                    "done_event": self.done_event,
                },
            )
            self.info_toast(self.tra("提示"), self.tra("AI 自动校对任务已开始，共处理 {} 个条目。").format(count))
    
    def _translate_selected_rows(self):
        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not selected_rows:
            return

        if Base.work_status != Base.STATUS.IDLE:
            self.warning(self.tra("正在执行其他任务中！"))
            return

        tasks_by_file = defaultdict(list)

        for row in selected_rows:
            meta_data = self._get_row_meta(row)
            source_item = self.table.item(row, self.COL_SOURCE)
            if not meta_data or not source_item:
                continue

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
                    "update_event": self.update_event,
                    "done_event": self.done_event,
                },
            )
            count += len(items_to_translate)

        if count > 0:
            self.info_toast(self.tra("提示"), self.tra("已提交 {} 个条目的翻译任务。").format(count))

    def _on_task_done(self, event, data: dict):
        if not self.isVisible():
            return

        operation = data.get("operation")
        status = data.get("status")
        updated_item_count = data.get("updated_item_count", 0)
        updated_file_count = data.get("updated_file_count", 0)

        if operation == "proofread":
            if status == "success":
                self.success_toast(self.tra("完成"), self.tra("AI 自动校对完成，已更新 {} 个文件中的 {} 条内容。").format(updated_file_count, updated_item_count))
            elif status == "empty":
                self.warning_toast(self.tra("提示"), self.tra("AI 自动校对结束，但没有可回写的结果。"))
        elif operation == "translate":
            if status == "success":
                self.success_toast(self.tra("完成"), self.tra("检查结果翻译完成，已更新 {} 条内容。").format(updated_item_count))
            elif status == "empty":
                self.warning_toast(self.tra("提示"), self.tra("检查结果翻译结束，但没有可回写的结果。"))

    def _delete_selected_rows(self):
        current_sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)

        selected_rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in selected_rows:
            self.table.removeRow(row)

        self.table.setSortingEnabled(current_sorting)
