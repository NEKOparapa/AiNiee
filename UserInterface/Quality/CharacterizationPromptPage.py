import copy
import rapidjson as json
from qfluentwidgets import (Action, FluentIcon, MessageBox, TableWidget, RoundMenu)

from PyQt5.QtCore import QEvent, Qt, QPoint
from PyQt5.QtWidgets import (QFrame, QFileDialog, QHeaderView, QLayout, QVBoxLayout,
                             QTableWidgetItem,QAbstractItemView)

from Base.Base import Base
from UserInterface.TableHelper.TableHelper import TableHelper
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface import AppFluentWindow

class CharacterizationPromptPage(QFrame, Base):

    KEYS = (
        "original_name",
        "translated_name",
        "gender",
        "age",
        "personality",
        "speech_style",
        "additional_info"
    )
    COLUMN_NAMES = {0: "原名",1: "译名",2: "性别", 3: "年龄",4: "性格",5: "说话风格",6: "补充信息"}

    def __init__(self, text: str, window: AppFluentWindow) -> None:
        super().__init__(parent=window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "characterization_switch": False,
            "characterization_data": [
                {
                    "original_name": "遠坂凛",
                    "translated_name": "远坂凛",
                    "gender": "女",
                    "age": "少女",
                    "personality": "高傲，自满",
                    "speech_style": "大小姐，严厉",
                    "additional_info": "在人前言谈举止高雅，对所有人都用敬语，但在熟人面前本性其实是个爱恶作剧和捉弄自己喜欢的人的小恶魔。"
                },
            ],
        }

        # 读取配置
        config = self.save_config(self.load_config_from_default())

        # 排序相关属性
        self._sort_column_index = -1  # 记录当前排序的列索引，-1表示未排序
        self._sort_order = Qt.AscendingOrder # 记录当前排序顺序

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_head(self.container, config, window)
        self.add_widget_body(self.container, config, window)
        self.add_widget_foot(self.container, config, window)

    def _get_translated_column_name(self, index: int) -> str:
        return self.tra(self.COLUMN_NAMES.get(index, f"字段{index+1}"))

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self.update_table() # 每次显示时更新，并确保搜索/排序状态重置

    def update_table(self) -> None:
        config = self.load_config()
        TableHelper.update_to_table(self.table, config["characterization_data"], CharacterizationPromptPage.KEYS)
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
            widget.set_checked(config.get("characterization_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["characterization_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自定义角色介绍"),
                self.tra("启用此功能后，将根据本页中设置的构建角色介绍，并补充到基础提示词中（不支持本地类模型）"),
                init=init,
                checked_changed=checked_changed,
            )
        )


    # 添加主体部件
    def add_widget_body(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:

        def item_changed(item: QTableWidgetItem) -> None:
            item.setTextAlignment(Qt.AlignCenter)
            # 编辑单元格后，不一定需要立即重排序或重置搜索
            # self.search_input.clear()
            # self._reset_sort_indicator()
            # 后期可以添加自动保存，也可以不添加


        self.table = TableWidget(self)
        parent.addWidget(self.table)

        self.table.setBorderRadius(8)
        self.table.setBorderVisible(True)
        self.table.setWordWrap(True)
        self.table.setColumnCount(len(CharacterizationPromptPage.KEYS))
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked | QAbstractItemView.EditKeyPressed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)

        self.table.itemChanged.connect(item_changed)

        header_labels = [self._get_translated_column_name(i) for i in range(len(CharacterizationPromptPage.KEYS))]
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
        data = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)

        # 3. 定义排序键函数
        try:
            sort_key_name = CharacterizationPromptPage.KEYS[logicalIndex]
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
        TableHelper.update_to_table(self.table, data, CharacterizationPromptPage.KEYS)
        self.table.resizeRowsToContents() # 重新调整行高
        self.table.setUpdatesEnabled(True)

        # 6. 更新表头排序指示器
        self.table.horizontalHeader().setSortIndicator(self._sort_column_index, self._sort_order)

        # 7. 重置搜索状态，因为行顺序已改变
        self.info_toast("", self.tra("表格已按 '{}' {}排序").format(
            self._get_translated_column_name(logicalIndex),
            self.tra("升序") if self._sort_order == Qt.AscendingOrder else self.tra("降序")
        ))


    # 底部命令栏
    def add_widget_foot(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:

        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)

        self.add_command_bar_action_save(self.command_bar_card, config, window)
        self.add_command_bar_action_reset(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_import(self.command_bar_card, config, window)
        self.add_command_bar_action_export(self.command_bar_card, config, window)

    # 保存
    def add_command_bar_action_save(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            config = self.load_config()
            config["characterization_data"] = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)
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
            config["characterization_data"] = copy.deepcopy(self.default.get("characterization_data", []))
            self.save_config(config)
            TableHelper.update_to_table(self.table, config.get("characterization_data"), CharacterizationPromptPage.KEYS)
            self.table.resizeRowsToContents()
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
            data = TableHelper.load_from_file(path, CharacterizationPromptPage.KEYS)
            config = self.load_config()

            # 去重逻辑
            current_data = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)
            current_src_set = {item['original_name'] for item in current_data if item.get('original_name')} # 处理潜在的空 original_name
            new_data_filtered = [item for item in data if item.get('original_name') and item['original_name'] not in current_src_set] # 确保导入的项目具有 original_name

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
            TableHelper.update_to_table(self.table, config["prompt_dictionary_data"], CharacterizationPromptPage.KEYS)
            self.table.resizeRowsToContents() # 导入后调整行高

            # 现在将可能已修改的表格状态保存回配置
            config["prompt_dictionary_data"] = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)
            self.save_config(config)
            self._reset_sort_indicator() # 导入后重置排序
            self.success_toast("", self.tra("数据已导入并更新") + f" ({len(new_data_filtered)} {self.tra('项')})...")

        parent.add_action(
            Action(FluentIcon.DOWNLOAD, self.tra("导入"), parent, triggered = triggered),
        )

    # 导出
    def add_command_bar_action_export(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            data = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)
            if not data:
                self.warning_toast("", self.tra("表格中没有数据可导出"))
                return

            default_filename = self.tra("导出_角色介绍") + ".json"
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

