import rapidjson as json
from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import TableWidget
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QLayout
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QTableWidgetItem

from Base.Base import Base
from UserInterface.TableHelper.TableHelper import TableHelper
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface import AppFluentWindow

class TranslationExamplePromptPage(QFrame, Base):

    # 表格每列对应的数据字段
    KEYS = (
        "src",
        "dst",
    )

    def __init__(self, text: str, window: AppFluentWindow) -> None:
        super().__init__(parent = window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "translation_example_switch": False,
            "translation_example_data" : [
                {
                    "src": "結婚前日、目の前の婚約者はそう言った。",
                    "dst": "婚前一日，其婚約者前，如是云。",
                }
            ],
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_head(self.container, config, window)
        self.add_widget_body(self.container, config, window)
        self.add_widget_foot(self.container, config, window)

    # 头部
    def add_widget_head(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:

        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("translation_example_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["translation_example_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自定义翻译示例"),
                self.tra("启用此功能后，将根据本页中设置的内容构建翻译示例，并补充到基础提示词中（不支持本地类模型）"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 主体
    def add_widget_body(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:

        def item_changed(item: QTableWidgetItem) -> None:
            item.setTextAlignment(Qt.AlignCenter)

        self.table = TableWidget(self)
        parent.addWidget(self.table)

        # 设置表格属性
        self.table.setBorderRadius(4)
        self.table.setBorderVisible(True)
        self.table.setWordWrap(False)
        self.table.setColumnCount(len(TranslationExamplePromptPage.KEYS))
        self.table.resizeRowsToContents() # 设置行高度自适应内容
        self.table.resizeColumnsToContents() # 设置列宽度自适应内容
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # 撑满宽度
        self.table.itemChanged.connect(item_changed)

        # 设置水平表头并隐藏垂直表头
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setHorizontalHeaderLabels(
            [
                "src",
                "dst",
            ],
        )

        # 向表格更新数据
        TableHelper.update_to_table(self.table, config.get("translation_example_data"), TranslationExamplePromptPage.KEYS)

    # 底部
    def add_widget_foot(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)

        # 添加命令
        self.add_command_bar_action_import(self.command_bar_card, config, window)
        self.add_command_bar_action_export(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_insert(self.command_bar_card, config, window)  # 新增插入行按钮
        self.add_command_bar_action_removeselectedline(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_save(self.command_bar_card, config, window)
        self.add_command_bar_action_reset(self.command_bar_card, config, window)

    # 导入
    def add_command_bar_action_import(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            # 选择文件
            path, _ = QFileDialog.getOpenFileName(None, self.tra("选择文件"), "", "json 文件 (*.json);;xlsx 文件 (*.xlsx)")
            if not isinstance(path, str) or path == "":
                return

            # 从文件加载数据
            data = TableHelper.load_from_file(path, TranslationExamplePromptPage.KEYS)

            # 读取配置文件
            config = self.load_config()
            config["translation_example_data"].extend(data)

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config["translation_example_data"], TranslationExamplePromptPage.KEYS)

            # 从表格加载数据（去重后）
            config["translation_example_data"] = TableHelper.load_from_table(self.table, TranslationExamplePromptPage.KEYS)

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            info_cont1 = self.tra("数据已导入") + "..."
            self.success_toast("", info_cont1)

        parent.add_action(
            Action(FluentIcon.DOWNLOAD, self.tra("导入"), parent, triggered = triggered),
        )

    # 导出
    def add_command_bar_action_export(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            # 加载配置文件
            config = self.load_config()

            # 从表格加载数据
            data = TableHelper.load_from_table(self.table, TranslationExamplePromptPage.KEYS)

            # 导出文件
            info_cont1 = self.tra("导出_翻译示例")+ ".json"
            with open(info_cont1, "w", encoding = "utf-8") as writer:
                writer.write(json.dumps(data, indent = 4, ensure_ascii = False))

            # 弹出提示
            info_cont2 = self.tra("数据已导出到应用根目录") + "..."
            self.success_toast("", info_cont2)

        parent.add_action(
            Action(FluentIcon.SHARE, self.tra("导出"), parent, triggered = triggered),
        )

    # 保存
    def add_command_bar_action_save(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            # 加载配置文件
            config = self.load_config()

            # 从表格加载数据
            config["translation_example_data"] = TableHelper.load_from_table(self.table, TranslationExamplePromptPage.KEYS)

            # 清空表格
            self.table.clearContents()

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config["translation_example_data"], TranslationExamplePromptPage.KEYS)

            # 从表格加载数据（去重后）
            config["translation_example_data"] = TableHelper.load_from_table(self.table, TranslationExamplePromptPage.KEYS)

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            info_cont1 = self.tra("数据已保存")+ " ... "
            self.success_toast("", info_cont1)

        parent.add_action(
            Action(FluentIcon.SAVE, self.tra("保存"), parent, triggered = triggered),
        )

    # 重置
    def add_command_bar_action_reset(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            info_cont1 = self.tra("是否确认重置为默认数据")  + " ... ？"
            message_box = MessageBox("Warning", info_cont1, window)
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消") )

            if not message_box.exec():
                return

            # 清空表格
            self.table.clearContents()

            # 加载配置文件
            config = self.load_config()

            # 加载默认设置
            config["translation_example_data"] = self.default.get("translation_example_data")

            # 保存配置文件
            config = self.save_config(config)

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config.get("translation_example_data"), TranslationExamplePromptPage.KEYS)

            # 弹出提示
            info_cont2 = self.tra("数据已重置")  + " ... "
            self.success_toast("", info_cont2)

        parent.add_action(
            Action(FluentIcon.DELETE, self.tra("重置"), parent, triggered = triggered),
        )

    # 移除选取行
    def add_command_bar_action_removeselectedline(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:
        def triggered() -> None:
            indices = self.table.selectionModel().selectedRows()
            if not indices:
                return
            
            for index in reversed(sorted(indices)):
                self.table.removeRow(index.row())

            self.table.selectRow(-1)

            # 提示操作完成
            info_cont = self.tra("选取行已移除") + "..."
            self.success_toast("", info_cont)


        parent.add_action(
            Action(FluentIcon.REMOVE_FROM, self.tra("移除选取行"), parent, triggered = triggered),
        )

    # 插入行
    def add_command_bar_action_insert(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            # 获取所有选中的行号（去重）
            selected_rows = {item.row() for item in self.table.selectedItems()}
            # 按降序排序以正确处理多选插入
            sorted_rows = sorted(selected_rows, reverse=True)

            if not sorted_rows:
                # 没有选中行时在末尾添加
                self.table.setRowCount(self.table.rowCount() + 1)
            else:
                for row in sorted_rows:
                    self.table.insertRow(row + 1)  # 在选中行下方插入

            # 提示操作完成
            info_cont = self.tra("新行已插入") + "..."
            self.success_toast("", info_cont)

        # 创建并添加Action到命令栏
        parent.add_action(
            Action(FluentIcon.ADD_TO, self.tra("插入行"), parent, triggered=triggered)
        )