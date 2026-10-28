from UserInterface.Table.MultiTablePageMixin import MultiTablePageMixin
import copy
from uuid import uuid4
from typing import TYPE_CHECKING
from qfluentwidgets import Action, FluentIcon, TableWidget, RoundMenu

from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QFrame, QHeaderView, QLayout, QVBoxLayout, QTableWidgetItem, QAbstractItemView

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Domain.PromptBuilder.GlossaryHelper import GlossaryHelper
from ModuleFolders.Log.Log import LogMixin
from UserInterface.Widget.Toast import ToastMixin
from UserInterface.Table.TableHelper.TableHelper import TableHelper
from ModuleFolders.Service.NameExtractor.NameExtractor import NameExtractor
from UserInterface.Widget.TerminologyMatchSettingsDialog import TerminologyMatchSettingsDialog
from UserInterface.Widget.SwitchTableItemDelegate import SwitchTableItemDelegate
from UserInterface.Native.FileDialogProvider import get_existing_directory

if TYPE_CHECKING:
    from UserInterface import AppFluentWindow

class PromptDictionaryPage(MultiTablePageMixin, QFrame, ConfigMixin, LogMixin, ToastMixin, Base):

    TABLE_KIND = "prompt_dictionary"
    TABLE_TITLE = "术语表"

    KEYS = ("src", "dst", "info", "regex",)
    SWITCH_KEYS = ("regex",)
    REGEX_COLUMN_INDEX = 3
    COLUMN_NAMES = {0: "原文",1: "译文",2: "描述",3: "正则",}
    INVALID_ROW_BRUSH = QBrush(QColor(255, 0, 0, 96))

    def __init__(self, text: str, window: "AppFluentWindow") -> None:
        super().__init__(parent=window)
        self.setObjectName(text.replace(" ", "-"))


        # 订阅术语表翻译完成事件
        self.subscribe(Base.EVENT.GLOSS_TASK_DONE, self.glossary_translation_done)
        # 读取配置
        config = self.update_config(lambda _config: None)
        self._init_multi_table_state(config)
        self._loaded_rows = None

        # 搜索相关属性
        self._search_results = []
        self._current_search_index = -1
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._perform_search)
        self._current_search_field_index = -1

        # 排序相关属性
        self._sort_column_index = -1
        self._sort_order = Qt.AscendingOrder

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_head(self.container, config, window)
        self.add_widget_body(self.container, config, window)
        self._finish_multi_table_setup()

    # 翻译字段名字
    def _get_translated_column_name(self, index: int) -> str:
        return self.tra(self.COLUMN_NAMES.get(index, f"字段{index+1}"))

    # 右键菜单内容
    def show_table_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self.table)
        has_selection = bool(self.table.selectionModel().selectedRows())

        if has_selection:
            menu.addAction(Action(FluentIcon.ADD_TO, self.tra("插入行"), triggered=self._handle_insert_row))
            menu.addAction(Action(FluentIcon.REMOVE_FROM, self.tra("删除行"), triggered=self._handle_remove_selected_rows))
            menu.addSeparator()

        row_count = self.table.rowCount()
        row_count_action = Action(FluentIcon.LEAF,f"{self.tra('全部行数')}: {row_count}")
        row_count_action.setEnabled(False)
        menu.addAction(row_count_action)

        global_pos = self.table.mapToGlobal(pos)
        menu.exec_(global_pos, ani=True)

    # 删除含操作
    def _handle_remove_selected_rows(self) -> None:
        indices = self.table.selectionModel().selectedRows()
        if not indices:
            return

        rows_to_remove = sorted([index.row() for index in indices], reverse=True)

        self.table.setUpdatesEnabled(False)
        for row in rows_to_remove:
            self.table.removeRow(row)
        self.table.setUpdatesEnabled(True)

        self._reset_search()
        self._reset_sort_indicator()
        self.success_toast("", self.tra("选取行已移除") + "...")

    # 插入行操作
    def _handle_insert_row(self) -> None:
        selected_rows = {item.row() for item in self.table.selectedItems()}
        insert_pos = self.table.rowCount()
        if selected_rows:
             insert_pos = max(selected_rows) + 1

        self.table.insertRow(insert_pos)
        new_item = QTableWidgetItem("")
        self.table.setItem(insert_pos, 0, new_item)
        self._sync_regex_cell(insert_pos)
        self.table.scrollToItem(new_item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table.selectRow(insert_pos)
        self.table.editItem(self.table.item(insert_pos, 0))

        self._reset_sort_indicator()
        self.success_toast("", self.tra("新行已插入") + "...")


    def _open_match_settings_dialog(self) -> None:
        current = self._current_table()
        if current is None:
            return
        table_id = current["id"]
        dialog = TerminologyMatchSettingsDialog(self.window(), match_options=current["match_options"])
        if dialog.exec():
            self._update_table_metadata(table_id, match_options=dialog.match_options)

    # 添加主题布局内容
    def add_widget_body(self, parent: QLayout, config: dict, window: "AppFluentWindow") -> None:
        toolbar_widget = self._create_search_toolbar()
        parent.addWidget(toolbar_widget)
        parent.setSpacing(10)

        def item_changed(item: QTableWidgetItem) -> None:
            previous = self.table.blockSignals(True)
            try:
                item.setTextAlignment(Qt.AlignCenter)
                if item.column() == 0:
                    self._sync_regex_cell(item.row())
                if item.column() in (0, self.REGEX_COLUMN_INDEX):
                    self._refresh_row_highlight(item.row())
            finally:
                self.table.blockSignals(previous)

        self.table = TableWidget(self)
        self.table.setItemDelegate(SwitchTableItemDelegate(self.table))
        parent.addWidget(self.table)

        self.table.setBorderRadius(8)
        self.table.setBorderVisible(True)
        self.table.setWordWrap(True)
        self.table.setColumnCount(len(PromptDictionaryPage.KEYS))
        self.table.verticalHeader().hide()
        TableHelper.style_public_table_editor(self.table)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            self.REGEX_COLUMN_INDEX,
            QHeaderView.Fixed,
        )
        self.table.setColumnWidth(self.REGEX_COLUMN_INDEX, 72)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.table.itemChanged.connect(item_changed)

        header_labels = [self._get_translated_column_name(i) for i in range(len(PromptDictionaryPage.KEYS))]
        self.table.setHorizontalHeaderLabels(header_labels)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().sectionClicked.connect(self._sort_table_by_column)
        self._reset_sort_indicator()

    def _reset_sort_indicator(self):
        self._sort_column_index = -1
        self._sort_order = Qt.AscendingOrder
        if hasattr(self, 'table'):
            self.table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)

    def _sort_table_by_column(self, logicalIndex: int):
        if self._sort_column_index == logicalIndex:
            self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self._sort_column_index = logicalIndex
            self._sort_order = Qt.AscendingOrder

        data = self._load_table_rows()
        try:
            sort_key_name = PromptDictionaryPage.KEYS[logicalIndex]
        except IndexError:
            self.logger.warning(f"Invalid column index {logicalIndex} for sorting.")
            return

        def get_sort_key(item):
            value = item.get(sort_key_name, "")
            if value is None:
                value = ""
            return str(value).lower()

        data.sort(key=get_sort_key, reverse=(self._sort_order == Qt.DescendingOrder))

        self.table.setUpdatesEnabled(False)
        self._update_table_rows(data)
        self.table.setUpdatesEnabled(True)
        self.table.horizontalHeader().setSortIndicator(self._sort_column_index, self._sort_order)
        self._reset_search()
        self.info_toast("", self.tra("表格已按 '{}' {}排序").format(
            self._get_translated_column_name(logicalIndex),
            self.tra("升序") if self._sort_order == Qt.AscendingOrder else self.tra("降序")
        ))


            #self.toggle_toolbar_button.setToolTip(self.tra("切换到副工具栏"))

    # 设置搜索字段
    def _set_search_field(self, field_index: int, field_name: str):
        self.search_field_button.setText(field_name)
        if self._current_search_field_index != field_index:
            self._current_search_field_index = field_index
            self._perform_search()

    # 搜索逻辑方法
    def _on_search_text_changed(self, text: str):
        if not text.strip():
             self._reset_search_results()
             self._update_search_ui()
             self.table.clearSelection()
        self._search_timer.start()

    # 重置搜索结果
    def _reset_search_results(self):
        self._search_results = []
        self._current_search_index = -1

    # 重置搜索状态
    def _reset_search(self):
        """重置搜索状态，但不影响排序状态。"""
        self._reset_search_results()
        if hasattr(self, 'search_input'):
            self.search_input.clear()
            self._current_search_field_index = -1
            if hasattr(self, 'search_field_button'): 
                 self.search_field_button.setText(self.tra("全部"))
            self._update_search_ui()
            if hasattr(self, 'table'): 
                 self.table.clearSelection()

    # 执行搜索
    def _perform_search(self):
        search_text = self.search_input.text().strip().lower()
        self._reset_search_results() # 清除之前的搜索结果

        if not search_text:
            self._update_search_ui()
            if hasattr(self, 'table'): self.table.clearSelection() 
            return

        target_col = self._current_search_field_index
        rows = self.table.rowCount()
        cols = self.table.columnCount()

        for r in range(rows):
            columns_to_search = range(cols) if target_col == -1 else [target_col]
            for c in columns_to_search:
                 # 确保列索引有效
                if c >= cols: continue 
                item = self.table.item(r, c)
                if item and search_text in item.text().lower():
                    self._search_results.append((r, c))
                    if target_col != -1: # 如果搜索特定列，则停止检查此行中的其他列
                         break

        # 如果搜索“全部”导致每行有多个匹配项，则删除重复行
        if target_col == -1:
            unique_results = []
            seen_rows = set()
            for r, c in self._search_results:
                if r not in seen_rows:
                    unique_results.append((r, c)) # 保留该行的第一个列匹配项
                    seen_rows.add(r)
            self._search_results = unique_results


        if self._search_results:
            self._navigate_search_result(0) # 转到第一个结果
        else:
            self._update_search_ui() # 更新UI以显示“0/0”
            if hasattr(self, 'table'): self.table.clearSelection() 

    # 更新搜索UI
    def _update_search_ui(self):
        count = len(self._search_results)
        if count > 0:
            label_text = f"{self._current_search_index + 1}/{count}"
        else:
            # 仅当有搜索文本时显示0/0，否则清除标签
            if hasattr(self, 'search_input') and self.search_input.text().strip(): 
                label_text = "0/0"
            else:
                label_text = "" # 如果没有搜索文本则清除

        if hasattr(self, 'search_results_label'): self.search_results_label.setText(label_text) 

        # 启用/禁用导航按钮
        can_navigate = count > 1
        if hasattr(self, 'search_prev_button'): self.search_prev_button.setEnabled(can_navigate and self._current_search_index > 0) 
        if hasattr(self, 'search_next_button'): self.search_next_button.setEnabled(can_navigate and self._current_search_index < count - 1) 
        # 如果只有一个结果，则禁用两个按钮
        if count <= 1:
            if hasattr(self, 'search_prev_button'): self.search_prev_button.setEnabled(False) 
            if hasattr(self, 'search_next_button'): self.search_next_button.setEnabled(False) 

    # 导航上一个结果
    def _navigate_previous(self):
        if self._search_results and self._current_search_index > 0:
            self._navigate_search_result(self._current_search_index - 1)

    # 导航下一个结果
    def _navigate_next(self):
        if self._search_results and self._current_search_index < len(self._search_results) - 1:
            self._navigate_search_result(self._current_search_index + 1)

    # 导航到搜索结果
    def _navigate_search_result(self, index: int):
        if not self._search_results or not (0 <= index < len(self._search_results)):
            return

        self._current_search_index = index
        row, col = self._search_results[index]

        # 确保行/列仍然有效
        if hasattr(self, 'table') and row < self.table.rowCount() and col < self.table.columnCount(): 
            item_to_select = self.table.item(row, 0) 
            if item_to_select:
                self.table.clearSelection() # 首先清除之前的选择
                self.table.setCurrentCell(row, col) # 选择特定的单元格
                self.table.selectRow(row) # 选择包含结果的整行
                self.table.scrollToItem(item_to_select, QAbstractItemView.ScrollHint.PositionAtCenter) # 平滑滚动

        self._update_search_ui() # 更新标签和按钮状态

    def _load_table_rows(self) -> list[dict]:
        return GlossaryHelper.normalize_rows(
            TableHelper.load_from_table(
                self.table,
                PromptDictionaryPage.KEYS,
                self.SWITCH_KEYS,
            )
        )

    def _get_translatable_rows(self, rows: list[dict] | None = None) -> list[dict]:
        normalized_rows = GlossaryHelper.normalize_rows(
            self._load_table_rows() if rows is None else rows
        )
        return [
            row for row in normalized_rows
            if row.get("src") and not row.get("dst") and GlossaryHelper.is_row_valid(row)
        ]

    def _update_table_rows(self, rows: list[dict] | None) -> None:
        # Keep the last value for each source, preserving the original order.
        unique_rows = {}
        for row in GlossaryHelper.normalize_rows(rows):
            if row["src"]:
                unique_rows[row["src"]] = row
        normalized_rows = list(unique_rows.values())
        previous = self.table.blockSignals(True)
        # The stack temporarily disables ancestor updates during showEvent.
        # Restore this widget's explicit state, not that inherited suspension.
        updates_enabled = not self.table.testAttribute(Qt.WA_ForceUpdatesDisabled)
        self.table.setUpdatesEnabled(False)
        try:
            self.table.clearContents()
            self.table.setRowCount(max(16, len(normalized_rows)))
            for row_index in range(self.table.rowCount()):
                row = normalized_rows[row_index] if row_index < len(normalized_rows) else {}
                for column_index, key in enumerate(self.KEYS):
                    item = QTableWidgetItem("" if key in self.SWITCH_KEYS else row.get(key, ""))
                    item.setTextAlignment(Qt.AlignCenter)
                    if key in self.SWITCH_KEYS:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        if row.get("src"):
                            item.setCheckState(Qt.Checked if row.get(key) else Qt.Unchecked)
                    self.table.setItem(row_index, column_index, item)
                self._set_row_highlight(row_index, GlossaryHelper.get_row_state(row))
        finally:
            self.table.blockSignals(previous)
            self.table.setUpdatesEnabled(updates_enabled)

    def _sync_regex_cell(self, row_index: int) -> None:
        source = self.table.item(row_index, 0)
        item = self.table.item(row_index, self.REGEX_COLUMN_INDEX)
        if item is None:
            item = QTableWidgetItem("")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_index, self.REGEX_COLUMN_INDEX, item)
        if source is not None and source.text().strip():
            if item.data(Qt.CheckStateRole) is None:
                item.setCheckState(Qt.Unchecked)
        else:
            item.setData(Qt.CheckStateRole, None)

    def _refresh_row_highlight(self, row_index: int) -> None:
        previous = self.table.blockSignals(True)
        try:
            first_item = self.table.item(row_index, 0)
            switch_item = self.table.item(row_index, self.REGEX_COLUMN_INDEX)
            row = {
                "src": first_item.text().strip() if isinstance(first_item, QTableWidgetItem) else "",
                "regex": switch_item is not None and switch_item.checkState() == Qt.Checked,
            }
            state = GlossaryHelper.get_row_state(row)
            self._set_row_highlight(row_index, state)
        finally:
            self.table.blockSignals(previous)

    def _set_row_highlight(self, row_index: int, state: str) -> None:
        if state == GlossaryHelper.STATE_INVALID:
            brush = self.INVALID_ROW_BRUSH
        else:
            brush = QBrush()

        for column_index in range(self.table.columnCount()):
            item = self.table.item(row_index, column_index)
            if not isinstance(item, QTableWidgetItem):
                continue

            item.setBackground(brush)


    def name_extractor(self) -> None:
        if self._current_table() is None:
            return
        path = get_existing_directory(self, self.tra("选择文件夹"), "")
        if not path:
            return
        try:
            rows = NameExtractor.extract_names_from_folder(self, path)
            if not rows:
                self.info_toast(self.tra("信息"), self.tra("在指定文件夹中未找到符合条件的角色名"))
                return
            if self._merge_current_rows(rows):
                self.success_toast("", self.tra("术语信息已提取并添加"))
        except Exception as error:
            self.error_toast(self.tra("提取失败"), str(error))

    def glossary_translation(self) -> None:
        if self._current_table() is None or not self._save_current_table():
            return
        if Base.work_status != Base.STATUS.IDLE:
            self.warning_toast("", self.tra("软件正在执行其他任务中，请稍后再试"))
            return
        rows = self._canonical_rows(self._load_table_rows())
        untranslated = self._get_translatable_rows(rows)
        if not untranslated:
            self.info_toast(self.tra("提示"), self.tra("没有需要翻译的术语"))
            return
        request_id = str(uuid4())
        self._pending_glossary_requests[request_id] = {
            "table_id": self._active_table_id,
            "rows": {row["src"]: copy.deepcopy(row) for row in untranslated},
        }
        Base.work_status = Base.STATUS.GLOSS_TASK
        self.emit(Base.EVENT.GLOSS_TASK_START, {
            "table_id": self._active_table_id,
            "request_id": request_id,
            "prompt_dictionary_data": rows,
        })
        self.info_toast(self.tra("提示"), self.tra("术语表翻译任务已开始..."))

    def glossary_translation_done(self, event: int, data: dict):
        request_id = data.get("request_id")
        pending = self._pending_glossary_requests.get(request_id)
        if pending is None or data.get("table_id") != pending["table_id"]:
            return
        Base.work_status = Base.STATUS.IDLE
        status = data.get("status")
        if status not in ("success", "partial"):
            self._pending_glossary_requests.pop(request_id, None)
            if status == "error":
                self.error_toast(self.tra("术语表翻译失败"), data.get("message", self.tra("未知错误")))
            else:
                self.info_toast(self.tra("提示"), self.tra("没有需要翻译的术语"))
            return
        if self._active_table_id == pending["table_id"] and not self._save_current_table():
            # Keep the result in memory when disk persistence fails.
            pending["result"] = data
            return
        translations = {
            row["src"]: row["dst"] for row in data.get("updated_data", []) or []
            if isinstance(row, dict) and row.get("src") and row.get("dst")
        }
        changed = []
        try:
            def update(config):
                target = next((table for table in config[self._table_key] if table["id"] == pending["table_id"]), None)
                if target is None:
                    return
                for row in target["rows"]:
                    original = pending["rows"].get(row.get("src"))
                    if original is not None and row == original and row["src"] in translations:
                        row["dst"] = translations[row["src"]]
                        changed.append(row["src"])
            config = self.update_config(update)
        except Exception as error:
            pending["result"] = data
            self.error_toast(self.tra("保存失败"), str(error))
            return
        self._pending_glossary_requests.pop(request_id, None)
        from ModuleFolders.Config.TableConfigHelper import TableConfigHelper
        self._tables = TableConfigHelper.get_tables(config, self.TABLE_KIND)
        if self._active_table_id == pending["table_id"]:
            self._display_current_table(force=True)
        self._refresh_tabs()
        if changed:
            self.success_toast("", self.tra("术语表翻译成功并已更新"))

    def save_data(self):
        if not self._save_current_table():
            return
        for pending in list(self._pending_glossary_requests.values()):
            result = pending.get("result")
            if result is not None:
                self.glossary_translation_done(Base.EVENT.GLOSS_TASK_DONE, result)
        self.success_toast("", self.tra("数据已保存") + " ... ")
