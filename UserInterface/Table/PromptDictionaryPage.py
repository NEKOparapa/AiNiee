import copy
import rapidjson as json
from qfluentwidgets import (Action, FluentIcon, MessageBox, TableWidget, RoundMenu,
                            LineEdit, DropDownPushButton, TransparentToolButton, BodyLabel)

from PyQt5.QtCore import QEvent, Qt, QPoint, QTimer
from PyQt5.QtWidgets import (QFrame, QFileDialog, QHeaderView, QLayout, QVBoxLayout,
                             QTableWidgetItem, QHBoxLayout, QWidget,QAbstractItemView)

from Base.Base import Base
from UserInterface.TableHelper.TableHelper import TableHelper
from UserInterface.NameExtractor.NameExtractor import NameExtractor
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface import AppFluentWindow

class PromptDictionaryPage(QFrame, Base):

    KEYS = ("src", "dst", "info",)
    COLUMN_NAMES = {0: "原文",1: "译文",2: "描述",}

    def __init__(self, text: str, window: AppFluentWindow) -> None:
        super().__init__(parent=window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "prompt_dictionary_switch": False,
            "prompt_dictionary_data": [],
        }

        # 订阅术语表翻译完成事件
        self.subscribe(Base.EVENT.GLOSS_TRANSLATION_DONE, self.glossary_translation_done)
        # 读取配置
        config = self.save_config(self.load_config_from_default())

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
        self.add_widget_foot(self.container, config, window)

        self._reset_search()

    def _get_translated_column_name(self, index: int) -> str:
        return self.tra(self.COLUMN_NAMES.get(index, f"字段{index+1}"))

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self.update_table() # 每次显示时更新，并确保搜索/排序状态重置

    def update_table(self) -> None:
        config = self.load_config()
        TableHelper.update_to_table(self.table, config["prompt_dictionary_data"], PromptDictionaryPage.KEYS)
        self._reset_search() # 重置搜索状态
        self._reset_sort_indicator() # 重置排序指示器

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
        self.table.scrollToItem(new_item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table.selectRow(insert_pos) # 选择新行
        self.table.editItem(self.table.item(insert_pos, 0)) # 开始编辑第一个单元格

        self._reset_sort_indicator() # 重置排序指示器
        self.success_toast("", self.tra("新行已插入") + "...")


    # 添加头部部件
    def add_widget_head(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:

        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("prompt_dictionary_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["prompt_dictionary_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("术语表"),
                self.tra("通过构建术语表来引导模型翻译，可实现统一翻译、补充信息等功能\n△触发机制: 文本含有原名  ◯填写示例:  ダリヤ  |  达莉雅  |  女性的名字"),
                init=init,
                checked_changed=checked_changed,
            )
        )


    # 添加主体部件
    def add_widget_body(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:
        toolbar_widget = self._create_search_toolbar()
        parent.addWidget(toolbar_widget)
        parent.setSpacing(10)

        def item_changed(item: QTableWidgetItem) -> None:
            item.setTextAlignment(Qt.AlignCenter)
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
        self.table.setColumnCount(len(PromptDictionaryPage.KEYS))
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)

        self.table.itemChanged.connect(item_changed)

        header_labels = [self._get_translated_column_name(i) for i in range(len(PromptDictionaryPage.KEYS))]
        self.table.setHorizontalHeaderLabels(header_labels)

        # 启用排序和连接信号
        self.table.setSortingEnabled(False) # 禁用内置排序
        self.table.horizontalHeader().setSortIndicatorShown(True) # 显示排序指示器空间
        self.table.horizontalHeader().sectionClicked.connect(self._sort_table_by_column) # 连接排序信号

        self.table.resizeRowsToContents() # 调整行高
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
        data = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)

        # 3. 定义排序键函数
        try:
            sort_key_name = PromptDictionaryPage.KEYS[logicalIndex]
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
        TableHelper.update_to_table(self.table, data, PromptDictionaryPage.KEYS)
        self.table.resizeRowsToContents() # 重新调整行高
        self.table.setUpdatesEnabled(True)

        # 6. 更新表头排序指示器
        self.table.horizontalHeader().setSortIndicator(self._sort_column_index, self._sort_order)

        # 7. 重置搜索状态，因为行顺序已改变
        self._reset_search() # 非常重要！
        self.info_toast("", self.tra("表格已按 '{}' {}排序").format(
            self._get_translated_column_name(logicalIndex),
            self.tra("升序") if self._sort_order == Qt.AscendingOrder else self.tra("降序")
        ))

    # 工具栏
    def _create_search_toolbar(self) -> QWidget:

        toolbar_widget = QWidget(self)
        layout = QHBoxLayout(toolbar_widget)
        layout.setContentsMargins(0, 0, 0, 0) # 工具栏本身无外部边距
        layout.setSpacing(8) # 工具栏项之间的间距

        # 1. 搜索输入框
        self.search_input = LineEdit(self)
        self.search_input.setPlaceholderText(self.tra("搜索表格内容..."))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_text_changed) # 使用计时器进行防抖
        layout.addWidget(self.search_input, 1) # 拉伸输入字段

        # 2. 搜索字段下拉菜单
        self.search_field_button = DropDownPushButton(self.tra("全部"), self)
        self.search_field_menu = RoundMenu(parent=self.search_field_button)

        # "全部"字段的Action
        all_action = Action(self.tra("全部"))
        all_action.triggered.connect(lambda: self._set_search_field(-1, self.tra("全部")))
        self.search_field_menu.addAction(all_action)
        self.search_field_menu.addSeparator()

        # 特定字段的Action
        for i, key in enumerate(PromptDictionaryPage.KEYS):
            col_name = self._get_translated_column_name(i)
            action = Action(col_name)
            # 使用带有默认参数捕获的lambda表达式以传递正确的索引和名称
            action.triggered.connect(lambda checked=False, index=i, name=col_name: self._set_search_field(index, name))
            self.search_field_menu.addAction(action)

        self.search_field_button.setMenu(self.search_field_menu)
        layout.addWidget(self.search_field_button)

        # 3. 搜索结果标签
        self.search_results_label = BodyLabel("", self)
        layout.addWidget(self.search_results_label)

        # 4. 导航按钮 (上/下箭头)
        self.search_prev_button = TransparentToolButton(FluentIcon.UP, self)
        self.search_prev_button.setToolTip(self.tra("上一个结果"))
        self.search_prev_button.clicked.connect(self._navigate_previous)
        self.search_prev_button.setEnabled(False) # 初始禁用
        layout.addWidget(self.search_prev_button)

        self.search_next_button = TransparentToolButton(FluentIcon.DOWN, self)
        self.search_next_button.setToolTip(self.tra("下一个结果"))
        self.search_next_button.clicked.connect(self._navigate_next)
        self.search_next_button.setEnabled(False) # 初始禁用
        layout.addWidget(self.search_next_button)

        return toolbar_widget

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


    # 底部命令栏
    def add_widget_foot(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:

        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)

        self.add_command_bar_action_save(self.command_bar_card, config, window)
        self.add_command_bar_action_reset(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_import(self.command_bar_card, config, window)
        self.add_command_bar_action_export(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_name_extractor(self.command_bar_card, config, window)
        self.add_command_bar_glossary_translation(self.command_bar_card, config, window)

    # 保存
    def add_command_bar_action_save(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            config = self.load_config()
            config["prompt_dictionary_data"] = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)
            self.save_config(config)
            self.success_toast("", self.tra("数据已保存") + " ... ")

        parent.add_action(
            Action(FluentIcon.SAVE, self.tra("保存"), parent, triggered = triggered),
        )

    # 重置
    def add_command_bar_action_reset(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            info_cont1 = self.tra("是否确认重置为默认数据") + " ... ？"
            message_box = MessageBox(self.tra("警告"), info_cont1, self.window())
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))

            if not message_box.exec():
                return

            self.table.setRowCount(0)
            config = self.load_config()
            config["prompt_dictionary_data"] = copy.deepcopy(self.default.get("prompt_dictionary_data", []))
            self.save_config(config)
            TableHelper.update_to_table(self.table, config.get("prompt_dictionary_data"), PromptDictionaryPage.KEYS)
            self.table.resizeRowsToContents()
            self._reset_search() # 重置后重置搜索
            self._reset_sort_indicator() # 重置后重置排序
            self.success_toast("", self.tra("数据已重置") + " ... ")

        parent.add_action(
            Action(FluentIcon.DELETE, self.tra("重置"), parent, triggered = triggered),
        )

    # 导入
    def add_command_bar_action_import(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            path, _ = QFileDialog.getOpenFileName(self, self.tra("选择文件"), "", "json 文件 (*.json);;xlsx 文件 (*.xlsx)")
            if not isinstance(path, str) or path == "":
                return
            data = TableHelper.load_from_file(path, PromptDictionaryPage.KEYS)
            config = self.load_config()

            # 去重逻辑
            current_data = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)
            current_src_set = {item['src'] for item in current_data if item.get('src')} # 处理潜在的空 src
            new_data_filtered = [item for item in data if item.get('src') and item['src'] not in current_src_set] # 确保导入的项目具有 src

            if not new_data_filtered and data: # 如果所有导入的项目都已存在，则通知
                self.info_toast(self.tra("信息"), self.tra("导入的数据项均已存在于当前表格中"))
                return
            elif not new_data_filtered and not data: # 如果文件为空或格式无效，则通知
                self.warning_toast(self.tra("警告"), self.tra("未从文件中加载到有效数据"))
                return

            # 更新并保存
            # 合并现有数据（来自表格状态）+ 新的已过滤数据
            combined_data = current_data + new_data_filtered
            config["prompt_dictionary_data"] = combined_data # 直接更新配置

            # 在再次从表格保存配置*之前*更新表格
            TableHelper.update_to_table(self.table, config["prompt_dictionary_data"], PromptDictionaryPage.KEYS)
            self.table.resizeRowsToContents() # 导入后调整行高

            # 现在将可能已修改的表格状态保存回配置
            config["prompt_dictionary_data"] = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)
            self.save_config(config)
            self._reset_search() # 导入后重置搜索
            self._reset_sort_indicator() # 导入后重置排序
            self.success_toast("", self.tra("数据已导入并更新") + f" ({len(new_data_filtered)} {self.tra('项')})...")

        parent.add_action(
            Action(FluentIcon.DOWNLOAD, self.tra("导入"), parent, triggered = triggered),
        )

    # 导出
    def add_command_bar_action_export(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            data = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)
            if not data:
                self.warning_toast("", self.tra("表格中没有数据可导出"))
                return

            default_filename = self.tra("导出_术语表") + ".json"
            path, _ = QFileDialog.getSaveFileName(self, self.tra("导出文件"), default_filename, "JSON 文件 (*.json)")

            if not path:
                return

            if path.lower().endswith(".json"):
                with open(path, "w", encoding="utf-8") as writer:
                    writer.write(json.dumps(data, indent=4, ensure_ascii=False))
            else:
                self.error_toast(self.tra("导出失败"), self.tra("不支持的文件扩展名"))
                return

            self.success_toast("", self.tra("数据已导出到") + f": {path}")

        parent.add_action(
            Action(FluentIcon.SHARE, self.tra("导出"), parent, triggered = triggered),
        )


    # 角色提取
    def add_command_bar_name_extractor(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:
        def triggered() -> None:

            path = QFileDialog.getExistingDirectory(self, self.tra("选择文件夹"), "")
            if not path:
                return

            try:
                data = NameExtractor.extract_names_from_folder(self, path)
                if not data:
                    self.info_toast(self.tra("信息"), self.tra("在指定文件夹中未找到符合条件的角色名"))
                    return

                config = self.load_config()

                # 去重逻辑
                current_data = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)
                current_src_set = {item['src'] for item in current_data if item.get('src')}
                new_data_filtered = [item for item in data if item.get('src') and item['src'] not in current_src_set]

                if not new_data_filtered:
                    self.info_toast(self.tra("信息"), self.tra("均已存在于术语表中"))
                    return

                # 更新并保存
                combined_data = current_data + new_data_filtered
                config["prompt_dictionary_data"] = combined_data

                TableHelper.update_to_table(self.table, config["prompt_dictionary_data"], PromptDictionaryPage.KEYS)
                self.table.resizeRowsToContents()

                config["prompt_dictionary_data"] = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)
                self.save_config(config)
                self._reset_search() # 提取后重置搜索
                self._reset_sort_indicator() # 提取后重置排序
                self.success_toast("", self.tra("术语信息已提取并添加") + f" ({len(new_data_filtered)} {self.tra('项')})...")

            except Exception as e:
                self.error_toast(self.tra("提取失败"), str(e))
                self.logger.error(f"Name extraction failed: {e}", exc_info=True)

        parent.add_action(
            Action(FluentIcon.PEOPLE, self.tra("角色提取"), parent, triggered=triggered),
        )

    # 简单翻译
    def add_command_bar_glossary_translation(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:
        def triggered() -> None:

            if Base.work_status == Base.STATUS.IDLE:
                Base.work_status = Base.STATUS.GLOSS_TRANSLATION
                config = self.load_config()
                platform_tag = config.get(f"target_platform")
                platform = config.get("platforms", {}).get(platform_tag)

                data = copy.deepcopy(platform)
                data["proxy_url"] = config.get("proxy_url")
                data["proxy_enable"] = config.get("proxy_enable")
                data["target_language"] = config.get("target_language")
                # 从表格加载当前数据以进行翻译
                data["prompt_dictionary_data"] = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)

                # 检查是否需要翻译
                if not any(item.get('src') and not item.get('dst') for item in data["prompt_dictionary_data"]):
                     self.info_toast(self.tra("提示"), self.tra("没有需要翻译的术语"))
                     Base.work_status = Base.STATUS.IDLE
                     return

                self.emit(Base.EVENT.GLOSS_TRANSLATION_START, data)
                self.info_toast(self.tra("提示"), self.tra("术语表翻译任务已开始..."))

            else:
                self.warning_toast("", self.tra("软件正在执行其他任务中，请稍后再试"))

        parent.add_action(
            Action(FluentIcon.SEND_FILL, self.tra("简单翻译"), parent, triggered=triggered),
        )

    # 术语表翻译完成
    def glossary_translation_done(self, event: int, data: dict):
        Base.work_status = Base.STATUS.IDLE
        status = data.get("status")

        if status == "null":
            self.error_toast("", self.tra("术语表内容为空") + "...")
            return
        elif status == "error":
            error_msg = data.get("message", self.tra("未知错误"))
            self.error_toast(self.tra("术语表翻译失败"), error_msg + "...")
            return
        elif status == "success":
            updated_data = data.get("updated_data") # 这是来自翻译的 {src, dst} 列表
            if not updated_data:
                self.warning_toast(self.tra("完成"), self.tra("翻译完成，但没有数据被更新"))
                return

            # 再次从表格加载当前数据以应用更新
            prompt_dictionary_data_table = TableHelper.load_from_table(self.table, PromptDictionaryPage.KEYS)
            # 创建一个映射表，用于根据 'src' 快速查找翻译后的 'dst'
            updated_map = {item['src']: item['dst'] for item in updated_data if item.get('src') and item.get('dst')}

            something_updated = False
            # 遍历当前显示在表格中的数据
            for i in range(len(prompt_dictionary_data_table)):
                src_text = prompt_dictionary_data_table[i].get("src")
                current_dst = prompt_dictionary_data_table[i].get("dst")

                # 如果 src 匹配，dst 存在于映射表中，并且当前 dst 为空，则更新
                if src_text in updated_map and (not current_dst or current_dst.strip() == ""): # 确保空字符串也被覆盖
                    prompt_dictionary_data_table[i]["dst"] = updated_map[src_text]
                    something_updated = True

            # --- 应用更新到表格和配置 ---
            if something_updated:
                # 使用修改后的数据更新表格UI
                self.table.setUpdatesEnabled(False)
                TableHelper.update_to_table(self.table, prompt_dictionary_data_table, PromptDictionaryPage.KEYS)
                self.table.resizeRowsToContents()
                self.table.setUpdatesEnabled(True)

                # 将更新后的数据保存回配置
                config = self.load_config()
                config["prompt_dictionary_data"] = prompt_dictionary_data_table # 保存修改后的列表
                self.save_config(config)
                self._reset_search() # 翻译更新表格后重置搜索
                self._reset_sort_indicator() # 翻译更新表格后重置排序
                self.success_toast("", self.tra("术语表翻译成功并已更新") + "...")
