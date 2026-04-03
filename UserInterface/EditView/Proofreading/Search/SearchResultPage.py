import os
import re

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QSizePolicy,
    QSpacerItem,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    CheckBox,
    FluentIcon as FIF,
    LineEdit,
    PrimaryPushButton,
    RoundMenu,
    StrongBodyLabel,
    TableWidget,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from UserInterface.Widget.Toast import ToastMixin


class SearchResultPage(ConfigMixin, ToastMixin, Base, QWidget):
    COL_FILE = 0
    COL_ROW = 1
    COL_SOURCE = 2
    COL_TRANS = 3

    def closeEvent(self, event):
        try:
            self.unsubscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)
        except Exception:
            pass
        super().closeEvent(event)

    def __init__(self, search_results: list, cache_manager, search_params: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchResultPage")

        self.cache_manager = cache_manager
        self.search_params = search_params
        self.search_results = list(search_results)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(10)

        self._init_replace_panel()

        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)

        self._populate_data(self.search_results)

        self.table.itemChanged.connect(self._on_item_changed)
        self.subscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)

    def _init_replace_panel(self):
        self.replace_panel = QWidget(self)
        self.replace_panel.setObjectName("replacePanel")

        panel_layout = QVBoxLayout(self.replace_panel)
        panel_layout.setContentsMargins(0, 0, 0, 5)
        panel_layout.setSpacing(8)

        row1_layout = QHBoxLayout()
        row2_layout = QHBoxLayout()

        row1_layout.addWidget(StrongBodyLabel(self.tra("查找内容:"), self))
        self.find_input = LineEdit(self)
        self.find_input.setPlaceholderText(self.tra("输入搜索内容..."))
        row1_layout.addWidget(self.find_input)

        row1_layout.addSpacing(20)

        row1_layout.addWidget(StrongBodyLabel(self.tra("替换为:"), self))
        self.replace_input = LineEdit(self)
        self.replace_input.setPlaceholderText(self.tra("输入替换后的文本..."))
        row1_layout.addWidget(self.replace_input)

        row2_layout.addWidget(StrongBodyLabel(self.tra("选项:"), self))
        self.case_checkbox = CheckBox(self.tra("区分大小写"), self)
        self.whole_word_checkbox = CheckBox(self.tra("全词匹配"), self)
        self.regex_checkbox = CheckBox(self.tra("正则模式"), self)

        row2_layout.addWidget(self.case_checkbox)
        row2_layout.addWidget(self.whole_word_checkbox)
        row2_layout.addWidget(self.regex_checkbox)
        row2_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.replace_all_button = PrimaryPushButton(self.tra("全部替换"), self)
        row2_layout.addWidget(self.replace_all_button)

        panel_layout.addLayout(row1_layout)
        panel_layout.addLayout(row2_layout)
        self.layout.addWidget(self.replace_panel)

        self.regex_checkbox.toggled.connect(self._on_regex_toggled)
        self.replace_all_button.clicked.connect(self._on_replace_all_clicked)

    def _on_regex_toggled(self, is_checked: bool):
        self.whole_word_checkbox.setEnabled(not is_checked)
        if is_checked:
            self.whole_word_checkbox.setChecked(False)

    def _init_table(self):
        self.headers = [self.tra("文件"), self.tra("行"), self.tra("原文"), self.tra("译文")]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self.table.setColumnWidth(self.COL_FILE, 150)
        self.table.setColumnWidth(self.COL_ROW, 55)
        self.table.setColumnWidth(self.COL_SOURCE, 300)
        self.table.setColumnWidth(self.COL_TRANS, 300)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def _populate_data(self, search_results: list):
        self.table.blockSignals(True)
        highlight_brush = QBrush(QColor(144, 238, 144, 100))

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

            trans_item = QTableWidgetItem(item.translated_text)
            self.table.setItem(row_idx, self.COL_TRANS, trans_item)

            if item.extra and item.extra.get("language_mismatch_translation", False):
                trans_item.setBackground(highlight_brush)

        self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() != self.COL_TRANS:
            return

        ref_item = self.table.item(item.row(), self.COL_ROW)
        if not ref_item:
            return

        file_path, text_index = ref_item.data(Qt.UserRole)
        self.cache_manager.update_item_text(
            storage_path=file_path,
            text_index=text_index,
            field_name="translated_text",
            new_text=item.text(),
        )

    def _show_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self)
        has_selection = bool(self.table.selectionModel().selectedRows())
        if has_selection:
            menu.addAction(Action(FIF.EXPRESSIVE_INPUT_ENTRY, self.tra("翻译文本"), triggered=self._translate_text))
            menu.addSeparator()
            menu.addAction(Action(FIF.DELETE, self.tra("删除项"), triggered=self._delete_selected_items))
            menu.addSeparator()

        row_count_action = Action(FIF.LEAF, self.tra("行数: {}").format(self.table.rowCount()))
        row_count_action.setEnabled(False)
        menu.addAction(row_count_action)
        menu.exec(self.table.mapToGlobal(pos))

    def _get_selected_rows_indices(self):
        return sorted(list(set(index.row() for index in self.table.selectedIndexes())))

    def _translate_text(self):
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return

        if Base.work_status != Base.STATUS.IDLE:
            self.info_toast(self.tra("提示"), self.tra("正在执行其他任务，请稍候。"))
            return

        by_file = {}
        for row in selected_rows:
            ref_item = self.table.item(row, self.COL_ROW)
            source_item = self.table.item(row, self.COL_SOURCE)
            if not ref_item or not source_item:
                continue

            file_path, text_index = ref_item.data(Qt.UserRole)
            by_file.setdefault(file_path, []).append(
                {
                    "text_index": text_index,
                    "source_text": source_item.text(),
                }
            )

        if not by_file:
            return

        Base.work_status = Base.STATUS.TABLE_TASK
        total = 0
        for file_path, items in by_file.items():
            try:
                language_stats = self.cache_manager.project.get_file(file_path).language_stats
            except Exception:
                language_stats = None

            self.emit(
                Base.EVENT.TABLE_TRANSLATE_START,
                {
                    "file_path": file_path,
                    "items_to_translate": items,
                    "language_stats": language_stats,
                },
            )
            total += len(items)

        self.info_toast(self.tra("提示"), self.tra("已提交 {} 行文本的翻译任务。").format(total))

    def _delete_selected_items(self):
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return

        to_remove = set()
        for row in selected_rows:
            ref_item = self.table.item(row, self.COL_ROW)
            if ref_item:
                file_path, text_index = ref_item.data(Qt.UserRole)
                to_remove.add((file_path, text_index))

        self.search_results = [
            result for result in self.search_results if (result[0], result[2].text_index) not in to_remove
        ]
        self._populate_data(self.search_results)
        self.success_toast(self.tra("操作完成"), self.tra("已从结果中移除 {} 项。").format(len(to_remove)))

    def _on_table_update(self, event, data: dict):
        file_path = data.get("file_path")
        if data.get("target_column_index") != 2:
            return

        updated_items = data.get("updated_items", {})
        if not file_path or not updated_items:
            return

        translation_status = data.get("translation_status", TranslationStatus.TRANSLATED)

        self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                ref_item = self.table.item(row, self.COL_ROW)
                if not ref_item:
                    continue

                row_file_path, text_index = ref_item.data(Qt.UserRole)
                if row_file_path != file_path or text_index not in updated_items:
                    continue

                new_text = updated_items[text_index]
                item = self.table.item(row, self.COL_TRANS)
                if item:
                    item.setText(new_text)
                else:
                    self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(new_text))

                self.cache_manager.update_generated_translation(
                    storage_path=file_path,
                    text_index=text_index,
                    new_text=new_text,
                    translation_status=translation_status,
                )
        finally:
            self.table.blockSignals(False)

        self.table.resizeRowsToContents()

    def _on_replace_all_clicked(self):
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        is_case_sensitive = self.case_checkbox.isChecked()
        is_whole_word = self.whole_word_checkbox.isChecked()
        is_regex = self.regex_checkbox.isChecked()

        if not find_text:
            self.error_toast(self.tra("失败"), self.tra("查找内容不能为空。"))
            return

        if is_regex:
            try:
                flags = 0 if is_case_sensitive else re.IGNORECASE
                re.compile(find_text, flags)
            except re.error as error:
                self.error_toast(self.tra("替换失败"), self.tra(f"无效的正则表达式：{error}"))
                return

        self.table.blockSignals(True)
        replacement_count = 0
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, self.COL_TRANS)
                if not item:
                    continue

                original_text = item.text()
                new_text = self._perform_replace(
                    original_text,
                    find_text,
                    replace_text,
                    is_case_sensitive,
                    is_whole_word,
                    is_regex,
                )
                if original_text == new_text:
                    continue

                item.setText(new_text)
                replacement_count += 1

                ref_item = self.table.item(row, self.COL_ROW)
                if not ref_item:
                    continue

                file_path, text_index = ref_item.data(Qt.UserRole)
                self.cache_manager.update_item_text(
                    storage_path=file_path,
                    text_index=text_index,
                    field_name="translated_text",
                    new_text=new_text,
                )
        finally:
            self.table.blockSignals(False)

        self.table.resizeRowsToContents()
        self.success_toast(self.tra("操作完成"), self.tra(f"共找到并替换了 {replacement_count} 处。"))

    def _perform_replace(self, text, find, replace, case_sensitive, whole_word, is_regex):
        if is_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.sub(find, replace, text, flags=flags)

        flags = 0 if case_sensitive else re.IGNORECASE
        if whole_word:
            pattern = r"\b" + re.escape(find) + r"\b"
            return re.sub(pattern, replace, text, flags=flags)

        if case_sensitive:
            return text.replace(find, replace)
        return re.sub(re.escape(find), replace, text, flags=flags)
