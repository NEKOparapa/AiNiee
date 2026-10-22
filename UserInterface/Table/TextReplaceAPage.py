from UserInterface.Table.MultiTablePageMixin import MultiTablePageMixin
from qfluentwidgets import Action, FluentIcon, TableWidget, RoundMenu
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QFrame, QHeaderView, QLayout, QVBoxLayout, QTableWidgetItem, QAbstractItemView

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Domain.RegexSwitchHelper import RegexSwitchHelper
from UserInterface.Widget.Toast import ToastMixin
from UserInterface.Table.TableHelper.TableHelper import TableHelper
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from UserInterface import AppFluentWindow

class TextReplaceAPage(MultiTablePageMixin, QFrame, ConfigMixin, LogMixin, ToastMixin, Base):

    TABLE_KIND = "pre_translation"
    TABLE_TITLE = "译前替换"

    KEYS = ("src", "dst", "regex",)
    SWITCH_KEYS = ("regex",)
    REGEX_COLUMN_INDEX = 2
    COLUMN_NAMES = {0: "原文本",1: "目标文本",2: "正则",}
    INVALID_ROW_BRUSH = QBrush(QColor(255, 0, 0, 96))

    def __init__(self, text: str, window: "AppFluentWindow") -> None:
        super().__init__(parent=window)
        self.setObjectName(text.replace(" ", "-"))


        # 读取配置
        config = self.update_config(lambda _config: None)
        self._init_multi_table_state(config)

        # 搜索相关属性
        self._search_results = []
        self._current_search_index = -1
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._perform_search)
        self._current_search_field_index = -1

        # 排序相关属性
        self._sort_column_index = -1  # 记录当前排序的列索引，-1表示未排序
        self._sort_order = Qt.AscendingOrder # 记录当前排序顺序

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_head(self.container, config, window)
        self.add_widget_body(self.container, config, window)
        self._finish_multi_table_setup()

        self._reset_search()

    def _get_translated_column_name(self, index: int) -> str:
        return self.tra(self.COLUMN_NAMES.get(index, f"字段{index+1}"))

    # 右键菜单
    def show_table_context_menu(self, pos: QPoint):

        menu = RoundMenu(parent=self.table)
        has_selection = bool(self.table.selectionModel().selectedRows())

        if has_selection:
            menu.addAction(Action(FluentIcon.ADD_TO, self.tra("插入行"), triggered=self._handle_insert_row))
            menu.addAction(Action(FluentIcon.REMOVE_FROM, self.tra("删除行"), triggered=self._handle_remove_selected_rows))
            menu.addSeparator()

        # 行数统计
        row_count = self.table.rowCount()
        row_count_action = Action(FluentIcon.LEAF,f"{self.tra('全部行数')}: {row_count}")
        row_count_action.setEnabled(False) # 使其不可点击，仅作为信息显示
        menu.addAction(row_count_action)

        global_pos = self.table.mapToGlobal(pos)
        menu.exec_(global_pos, ani=True)

    # 处理删除选定行
    def _handle_remove_selected_rows(self) -> None:

        indices = self.table.selectionModel().selectedRows()
        if not indices:
            return

        rows_to_remove = sorted([index.row() for index in indices], reverse=True)

        self.table.setUpdatesEnabled(False)
        for row in rows_to_remove:
            self.table.removeRow(row)
        self.table.setUpdatesEnabled(True)

        self._reset_search() # 删除行后重置搜索
        self._reset_sort_indicator() # 删除行后重置排序
        self.success_toast("", self.tra("选取行已移除") + "...")

    # 处理插入行
    def _handle_insert_row(self) -> None:

        selected_rows = {item.row() for item in self.table.selectedItems()}
        insert_pos = self.table.rowCount() # 默认为末尾
        if selected_rows:
             insert_pos = max(selected_rows) + 1

        self.table.insertRow(insert_pos)
        # 滚动到新行
        new_item = QTableWidgetItem("") # 创建一个虚拟项以滚动到该位置
        self.table.setItem(insert_pos, 0, new_item) # 添加到第一列
        TableHelper.clear_switch_cell(
            self.table,
            insert_pos,
            self.REGEX_COLUMN_INDEX,
        )
        self.table.scrollToItem(new_item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table.selectRow(insert_pos) # 选择新行
        self.table.editItem(self.table.item(insert_pos, 0)) # 开始编辑第一个单元格

        self._reset_sort_indicator() # 重置排序指示器
        self.success_toast("", self.tra("新行已插入") + "...")


    # 添加主体部件
    def add_widget_body(self, parent: QLayout, config: dict, window: "AppFluentWindow") -> None:
        toolbar_widget = self._create_search_toolbar()
        parent.addWidget(toolbar_widget)
        parent.setSpacing(10)

        def item_changed(item: QTableWidgetItem) -> None:
            item.setTextAlignment(Qt.AlignCenter)
            if item.column() == 0:
                TableHelper.sync_switch_cell(
                    self.table,
                    item.row(),
                    0,
                    self.REGEX_COLUMN_INDEX,
                    self._on_regex_switch_changed,
                )
                self._refresh_row_highlight()
            # 编辑单元格后，不一定需要立即重排序或重置搜索
            # self._reset_search()
            # self.search_input.clear()
            # self._reset_sort_indicator()
            # 后期可以添加自动保存，也可以不添加


        self.table = TableWidget(self)
        parent.addWidget(self.table)

        self.table.setBorderRadius(8)
        self.table.setBorderVisible(True)
        self.table.setWordWrap(True)
        self.table.setColumnCount(len(TextReplaceAPage.KEYS))
        self.table.verticalHeader().hide()
        TableHelper.style_public_table_editor(self.table)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            self.REGEX_COLUMN_INDEX,
            QHeaderView.ResizeToContents,
        )
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)

        self.table.itemChanged.connect(item_changed)

        header_labels = [self._get_translated_column_name(i) for i in range(len(TextReplaceAPage.KEYS))]
        self.table.setHorizontalHeaderLabels(header_labels)

        # 启用排序和连接信号
        self.table.setSortingEnabled(False) # 禁用内置排序
        self.table.horizontalHeader().setSortIndicatorShown(True) # 显示排序指示器空间
        self.table.horizontalHeader().sectionClicked.connect(self._sort_table_by_column) # 连接排序信号

        self._reset_sort_indicator() # 重置排序指示器

    # 重置排序指示器
    def _reset_sort_indicator(self):
        """清除排序状态和表头的排序指示器。"""
        self._sort_column_index = -1
        self._sort_order = Qt.AscendingOrder
        if hasattr(self, 'table'): 
            self.table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)

    # 排序逻辑处理函数
    def _sort_table_by_column(self, logicalIndex: int):
        """当表头被点击时，按该列对表格数据进行排序。"""
        # 1. 确定排序顺序
        if self._sort_column_index == logicalIndex:
            # 如果点击的是同一列，切换排序顺序
            self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            # 如果点击的是新列，重置为升序
            self._sort_column_index = logicalIndex
            self._sort_order = Qt.AscendingOrder

        # 2. 获取当前表格数据
        data = self._load_table_rows()

        # 3. 定义排序键函数
        try:
            sort_key_name = TextReplaceAPage.KEYS[logicalIndex]
        except IndexError:
            self.logger.warning(f"Invalid column index {logicalIndex} for sorting.")
            return # 无效列索引，不排序

        def get_sort_key(item):
            value = item.get(sort_key_name, "") # 获取值，默认为空字符串
            if value is None: # 处理 None 值
                value = ""
            # 尝试将值转为小写字符串进行不区分大小写的文本排序
            # 注意：如果列包含数字或需要特定类型排序，这里可能需要更复杂的逻辑
            return str(value).lower()

        # 4. 排序数据
        data.sort(key=get_sort_key, reverse=(self._sort_order == Qt.DescendingOrder))


        # 5. 清空并重新填充表格
        self.table.setUpdatesEnabled(False) # 优化性能
        self.table.setRowCount(0) # 清空表格
        self._update_table_rows(data)
        self.table.setUpdatesEnabled(True)

        # 6. 更新表头排序指示器
        self.table.horizontalHeader().setSortIndicator(self._sort_column_index, self._sort_order)

        # 7. 重置搜索状态，因为行顺序已改变
        self._reset_search() # 非常重要！
        self.info_toast("", self.tra("表格已按 '{}' {}排序").format(
            self._get_translated_column_name(logicalIndex),
            self.tra("升序") if self._sort_order == Qt.AscendingOrder else self.tra("降序")
        ))


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
        return RegexSwitchHelper.normalize_replacement_rows(
            TableHelper.load_from_table(self.table, self.KEYS, self.SWITCH_KEYS)
        )

    def _update_table_rows(self, rows: list[dict] | None) -> None:
        normalized_rows = RegexSwitchHelper.normalize_replacement_rows(rows)
        previous = self.table.blockSignals(True)
        TableHelper.update_to_table(
            self.table,
            normalized_rows,
            self.KEYS,
            self.SWITCH_KEYS,
            self._on_regex_switch_changed,
        )
        self.table.blockSignals(previous)
        self._refresh_row_highlight()

    def _on_regex_switch_changed(self, _checked: bool) -> None:
        self._refresh_row_highlight()

    def _refresh_row_highlight(self) -> None:
        previous = self.table.blockSignals(True)
        for row_index in range(self.table.rowCount()):
            first_item = self.table.item(row_index, 0)
            switch = TableHelper.get_switch_from_cell(self.table, row_index, self.REGEX_COLUMN_INDEX)
            row = {
                "src": first_item.text().strip() if isinstance(first_item, QTableWidgetItem) else "",
                "regex": switch.isChecked() if switch is not None else False,
            }
            brush = self.INVALID_ROW_BRUSH if not RegexSwitchHelper.is_valid_re_pattern(row, "src") else QBrush()
            for column_index in range(self.table.columnCount()):
                item = self.table.item(row_index, column_index)
                if isinstance(item, QTableWidgetItem):
                    item.setBackground(brush)
        self.table.blockSignals(previous)
