import os
from collections import defaultdict

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, PrimaryPushButton, StrongBodyLabel

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from UserInterface.Widget.AutoHeightTableWidget import AutoHeightTableWidget
from UserInterface.Widget.Toast import ToastMixin


class SymbolRepairResultPage(ConfigMixin, LogMixin, ToastMixin, Base, QWidget):
    COL_FILE = 0
    COL_ROW = 1
    COL_SOURCE = 2
    COL_BEFORE = 3
    COL_AFTER = 4

    def __init__(self, result_data: dict, cache_manager=None, parent=None):
        super().__init__(parent)
        self.cache_manager = cache_manager
        self.repair_rows = result_data.get("repair_rows", [])
        self.setObjectName("SymbolRepairResultPage")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 8)
        self.layout.setSpacing(6)

        self._init_action_bar()

        self.table = AutoHeightTableWidget(self)
        self.layout.addWidget(self.table)

        self._init_table()
        self._populate_data()

    def _init_action_bar(self):
        action_bar = QWidget(self)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(0, 0, 0, 4)
        action_layout.setSpacing(8)

        self.result_table_label = StrongBodyLabel(self.tra("符号修复结果"), action_bar)
        action_layout.addWidget(self.result_table_label)

        self.count_label = CaptionLabel(
            self.tra("共 {0} 条需要修复").format(len(self.repair_rows)),
            action_bar,
        )
        action_layout.addWidget(self.count_label)

        action_layout.addStretch(1)

        self.apply_button = PrimaryPushButton(self.tra("应用全部修复"), action_bar)
        self.apply_button.setEnabled(bool(self.repair_rows))
        self.apply_button.clicked.connect(self._apply_all_repairs)
        action_layout.addWidget(self.apply_button)

        self.layout.addWidget(action_bar)

    def _init_table(self):
        headers = [
            self.tra("文件"),
            self.tra("行"),
            self.tra("原文"),
            self.tra("修复前"),
            self.tra("修复后"),
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
        self.table.setAutoHeightColumns((self.COL_SOURCE, self.COL_BEFORE, self.COL_AFTER))
        self.table.setMultilineEditColumns((self.COL_AFTER,))

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(False)

        self.table.setColumnWidth(self.COL_FILE, 110)
        self.table.setColumnWidth(self.COL_ROW, 70)
        self.table.setColumnWidth(self.COL_SOURCE, 260)
        self.table.setColumnWidth(self.COL_BEFORE, 260)

    def _build_row_meta(self, data: dict) -> dict:
        return {
            "file_path": data.get("file_path"),
            "text_index": data.get("text_index"),
            "translation_status": data.get("translation_status", TranslationStatus.TRANSLATED),
        }

    def _populate_data(self):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.repair_rows))

        for row, data in enumerate(self.repair_rows):
            file_path = data.get("file_path", "")
            text_index = data.get("text_index")
            row_number = data.get("row_number", (text_index + 1) if text_index is not None else "")

            file_item = QTableWidgetItem(os.path.basename(file_path) if file_path else "")
            file_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, self.COL_FILE, file_item)

            row_item = QTableWidgetItem(str(row_number))
            row_item.setTextAlignment(Qt.AlignCenter)
            row_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            row_item.setData(Qt.UserRole, self._build_row_meta(data))
            self.table.setItem(row, self.COL_ROW, row_item)

            source_item = QTableWidgetItem(data.get("source", ""))
            source_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, self.COL_SOURCE, source_item)

            before_item = QTableWidgetItem(data.get("before_text", ""))
            before_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, self.COL_BEFORE, before_item)

            after_item = QTableWidgetItem(data.get("check_text", ""))
            after_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(row, self.COL_AFTER, after_item)

        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

    def _get_row_meta(self, row: int) -> dict | None:
        row_item = self.table.item(row, self.COL_ROW)
        if not row_item:
            return None
        return row_item.data(Qt.UserRole)

    def _apply_all_repairs(self):
        if not self.cache_manager:
            return

        updated_by_file = defaultdict(dict)
        status_by_file = defaultdict(lambda: TranslationStatus.TRANSLATED)

        for row in range(self.table.rowCount()):
            meta_data = self._get_row_meta(row)
            if not meta_data:
                continue

            file_path = meta_data.get("file_path")
            text_index = meta_data.get("text_index")
            translation_status = meta_data.get("translation_status", TranslationStatus.TRANSLATED)
            if file_path is None or text_index is None:
                continue

            after_item = self.table.item(row, self.COL_AFTER)
            new_text = after_item.text() if after_item else ""
            updated_by_file[file_path][text_index] = new_text
            status_by_file[file_path] = translation_status

            self.cache_manager.update_generated_translation(
                storage_path=file_path,
                text_index=text_index,
                new_text=new_text,
                translation_status=translation_status,
            )

        total_count = sum(len(items) for items in updated_by_file.values())
        if total_count == 0:
            return

        # 通知已打开的文件表格刷新
        for file_path, updated_items in updated_by_file.items():
            self.emit(
                Base.EVENT.TABLE_BASIC_UPDATE,
                {
                    "file_path": file_path,
                    "target_column_index": 2,
                    "updated_items": updated_items,
                    "translation_status": status_by_file[file_path],
                },
            )

        self.apply_button.setEnabled(False)
        self.success_toast(self.tra("完成"), self.tra("已应用 {0} 条符号修复。").format(total_count))
        self.info("符号修复已应用，共 {} 条。".format(total_count))
