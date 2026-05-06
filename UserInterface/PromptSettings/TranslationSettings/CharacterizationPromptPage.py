import copy

import rapidjson as json
from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import Action, FluentIcon, MessageBox, RoundMenu, StrongBodyLabel, TableWidget, ToolButton

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Domain.PromptBuilder.CharacterHelper import CharacterHelper
from ModuleFolders.Log.Log import LogMixin
from UserInterface.Native.FileDialogProvider import get_open_file_name, get_save_file_name
from UserInterface.Table.TableHelper.TableHelper import TableHelper
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface.Widget.Toast import ToastMixin


class CharacterizationPromptPage(QFrame, ConfigMixin, LogMixin, ToastMixin, Base):
    KEYS = (
        "original_name",
        "translated_name",
        "gender",
        "age",
        "personality",
        "speech_style",
        "additional_info",
    )
    COLUMN_NAMES = {
        0: "原名",
        1: "译名",
        2: "性别",
        3: "年龄",
        4: "性格",
        5: "说话风格",
        6: "补充信息",
    }
    # 只在匹配逻辑不合法时标红，保存本身不拦截。
    INVALID_ROW_BRUSH = QBrush(QColor(255, 0, 0, 96))

    def __init__(self, text: str, window) -> None:
        super().__init__(parent=window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "characterization_switch": False,
            "characterization_data": [
                {
                    "original_name": "远坂[Separator]凛",
                    "translated_name": "远坂凛",
                    "gender": "女",
                    "age": "少女",
                    "personality": "高傲，自满",
                    "speech_style": "大小姐，严厉",
                    "additional_info": "在人前言谈举止高雅，对所有人都用敬语，但在熟人面前本性其实是一个爱恶作剧和捉弄自己喜欢的人的小恶魔。",
                },
            ],
        }

        config = self.save_config(self.load_config_from_default())

        self._sort_column_index = -1
        self._sort_order = Qt.AscendingOrder

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_head(self.container, config)
        self.add_widget_body(self.container)

    def _get_translated_column_name(self, index: int) -> str:
        return self.tra(self.COLUMN_NAMES.get(index, f"字段{index + 1}"))

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self.update_table()

    def update_table(self) -> None:
        config = self.load_config()
        normalized_rows = CharacterHelper.normalize_rows(config.get("characterization_data", []))
        self._update_table_rows(normalized_rows)
        self._reset_sort_indicator()

    def _update_table_rows(self, rows: list[dict] | None) -> None:
        self.table.setRowCount(0)
        TableHelper.update_to_table(self.table, rows, CharacterizationPromptPage.KEYS)
        self.table.resizeRowsToContents()
        self._refresh_invalid_row_highlight(rows)

    def _refresh_invalid_row_highlight(self, rows: list[dict] | None) -> None:
        validity_by_name = {}
        for row in rows or []:
            name = str(row.get("original_name", "") or "").strip()
            if not name:
                continue

            validity_by_name[name] = bool(row.get(CharacterHelper.VALID_KEY, True))

        for row_index in range(self.table.rowCount()):
            first_item = self.table.item(row_index, 0)
            name = first_item.text().strip() if isinstance(first_item, QTableWidgetItem) else ""
            is_invalid = bool(name) and not validity_by_name.get(name, True)
            self._set_row_highlight(row_index, is_invalid)

    def _set_row_highlight(self, row_index: int, highlighted: bool) -> None:
        for column_index in range(self.table.columnCount()):
            item = self.table.item(row_index, column_index)
            if not isinstance(item, QTableWidgetItem):
                continue

            item.setBackground(self.INVALID_ROW_BRUSH if highlighted else QBrush())

    def show_table_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self.table)
        has_selection = bool(self.table.selectionModel().selectedRows())

        if has_selection:
            menu.addAction(Action(FluentIcon.ADD_TO, self.tra("插入行"), triggered=self._handle_insert_row))
            menu.addAction(Action(FluentIcon.REMOVE_FROM, self.tra("删除行"), triggered=self._handle_remove_selected_rows))
            menu.addSeparator()

        row_count_action = Action(FluentIcon.LEAF, f"{self.tra('全部行数')}: {self.table.rowCount()}")
        row_count_action.setEnabled(False)
        menu.addAction(row_count_action)
        menu.exec_(self.table.mapToGlobal(pos), ani=True)

    def _handle_remove_selected_rows(self) -> None:
        indices = self.table.selectionModel().selectedRows()
        if not indices:
            return

        rows_to_remove = sorted([index.row() for index in indices], reverse=True)
        self.table.setUpdatesEnabled(False)
        for row in rows_to_remove:
            self.table.removeRow(row)
        self.table.setUpdatesEnabled(True)

        self._reset_sort_indicator()
        self.success_toast("", self.tra("选取行已移除") + "...")

    def _handle_insert_row(self) -> None:
        selected_rows = {item.row() for item in self.table.selectedItems()}
        insert_pos = max(selected_rows) + 1 if selected_rows else self.table.rowCount()

        self.table.insertRow(insert_pos)
        new_item = QTableWidgetItem("")
        self.table.setItem(insert_pos, 0, new_item)
        self.table.scrollToItem(new_item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table.selectRow(insert_pos)
        self.table.editItem(self.table.item(insert_pos, 0))

        self._reset_sort_indicator()
        self.success_toast("", self.tra("新行已插入") + "...")

    def add_widget_head(self, parent: QLayout, config: dict) -> None:
        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("characterization_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            current_config = self.load_config()
            current_config["characterization_switch"] = checked
            self.save_config(current_config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自定义角色介绍"),
                self.tra(
                    "启用此功能后，将根据本页中设置的内容构建角色介绍，并补充到基础提示词中\n可使用分隔符[Separator]来分隔姓和名"
                ),
                init=init,
                checked_changed=checked_changed,
            )
        )

    def add_widget_body(self, parent: QLayout) -> None:
        parent.addWidget(self._create_action_toolbar())

        def item_changed(item: QTableWidgetItem) -> None:
            item.setTextAlignment(Qt.AlignCenter)

        self.table = TableWidget(self)
        parent.addWidget(self.table)

        self.table.setBorderRadius(8)
        self.table.setBorderVisible(True)
        self.table.setWordWrap(True)
        self.table.setColumnCount(len(CharacterizationPromptPage.KEYS))
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.table.itemChanged.connect(item_changed)
        self.table.setHorizontalHeaderLabels(
            [self._get_translated_column_name(i) for i in range(len(CharacterizationPromptPage.KEYS))]
        )
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().sectionClicked.connect(self._sort_table_by_column)
        self.table.resizeRowsToContents()
        self._reset_sort_indicator()

    def _create_action_toolbar(self) -> QWidget:
        toolbar_widget = QWidget(self)
        layout = QHBoxLayout(toolbar_widget)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(StrongBodyLabel(self.tra("角色介绍表"), self))
        layout.addStretch(1)

        save_button = ToolButton(FluentIcon.SAVE, self)
        save_button.setToolTip(self.tra("保存"))
        save_button.clicked.connect(self.save_data)
        layout.addWidget(save_button)

        reset_button = ToolButton(FluentIcon.DELETE, self)
        reset_button.setToolTip(self.tra("重置"))
        reset_button.clicked.connect(self.reset_data)
        layout.addWidget(reset_button)

        import_button = ToolButton(FluentIcon.DOWNLOAD, self)
        import_button.setToolTip(self.tra("导入"))
        import_button.clicked.connect(self.import_data)
        layout.addWidget(import_button)

        export_button = ToolButton(FluentIcon.SHARE, self)
        export_button.setToolTip(self.tra("导出"))
        export_button.clicked.connect(self.export_data)
        layout.addWidget(export_button)

        return toolbar_widget

    def _reset_sort_indicator(self):
        self._sort_column_index = -1
        self._sort_order = Qt.AscendingOrder
        if hasattr(self, "table"):
            self.table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)

    def _sort_table_by_column(self, logical_index: int):
        if self._sort_column_index == logical_index:
            self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self._sort_column_index = logical_index
            self._sort_order = Qt.AscendingOrder

        try:
            sort_key_name = CharacterizationPromptPage.KEYS[logical_index]
        except IndexError:
            self.logger.warning(f"Invalid column index {logical_index} for sorting.")
            return

        data = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)
        data.sort(
            key=lambda item: str(item.get(sort_key_name, "") or "").lower(),
            reverse=(self._sort_order == Qt.DescendingOrder),
        )

        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)
        TableHelper.update_to_table(self.table, data, CharacterizationPromptPage.KEYS)
        self.table.resizeRowsToContents()
        self.table.setUpdatesEnabled(True)
        self.table.horizontalHeader().setSortIndicator(self._sort_column_index, self._sort_order)

        self.info_toast(
            "",
            self.tra("表格已按 '{}' {}排序").format(
                self._get_translated_column_name(logical_index),
                self.tra("升序") if self._sort_order == Qt.AscendingOrder else self.tra("降序"),
            ),
        )

    def save_data(self) -> None:
        config = self.load_config()
        rows = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)
        normalized_rows = CharacterHelper.normalize_rows(rows)
        config["characterization_data"] = normalized_rows
        self.save_config(config)
        # 立即重绘一次，让非法条目变红
        self._update_table_rows(normalized_rows)
        self.success_toast("", self.tra("数据已保存") + " ... ")

    def reset_data(self) -> None:
        message_box = MessageBox(self.tra("警告"), self.tra("是否确认重置为默认数据?") + " ... ？", self.window())
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))
        if not message_box.exec():
            return

        self.table.setRowCount(0)
        config = self.load_config()
        config["characterization_data"] = copy.deepcopy(self.default.get("characterization_data", []))
        self.save_config(config)
        self.update_table()
        self.success_toast("", self.tra("数据已重置") + " ... ")

    def import_data(self) -> None:
        path, _ = get_open_file_name(
            self,
            self.tra("选择文件"),
            "",
            "json 文件 (*.json);;xlsx 文件 (*.xlsx)",
        )
        if not isinstance(path, str) or path == "":
            return

        data = TableHelper.load_from_file(path, CharacterizationPromptPage.KEYS)
        config = self.load_config()
        current_data = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)
        current_src_set = {item["original_name"] for item in current_data if item.get("original_name")}
        new_data_filtered = [
            item
            for item in data
            if item.get("original_name") and item["original_name"] not in current_src_set
        ]

        if not new_data_filtered and data:
            self.info_toast(self.tra("信息"), self.tra("导入的数据项均已存在于当前表格中"))
            return
        if not new_data_filtered and not data:
            self.warning_toast(self.tra("警告"), self.tra("未从文件中加载到有效数据"))
            return

        combined_data = CharacterHelper.normalize_rows(current_data + new_data_filtered)
        config["characterization_data"] = combined_data
        self._update_table_rows(config["characterization_data"])
        self.save_config(config)
        self._reset_sort_indicator()
        self.success_toast("", self.tra("数据已导入并更新") + f" ({len(new_data_filtered)} {self.tra('项')})...")

    def export_data(self) -> None:
        data = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)
        if not data:
            self.warning_toast("", self.tra("表格中没有数据可导出"))
            return

        default_filename = self.tra("导出_角色介绍") + ".json"
        path, _ = get_save_file_name(
            self,
            self.tra("导出文件"),
            default_filename,
            "JSON 文件 (*.json)",
        )
        if not path:
            return

        if path.lower().endswith(".json"):
            with open(path, "w", encoding="utf-8") as writer:
                writer.write(json.dumps(data, indent=4, ensure_ascii=False))
        else:
            self.error_toast(self.tra("导出失败"), self.tra("不支持的文件扩展名"))
            return

        self.success_toast("", self.tra("数据已导出到") + f": {path}")
