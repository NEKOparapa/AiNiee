import rapidjson as json
from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import TableWidget
from PyQt5.QtCore import QEvent, Qt
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

class ExclusionListPage(QFrame, Base):

    # 表格每列对应的数据字段
    KEYS = (
        "markers",
        "info",
        "regex",
    )

    def __init__(self, text: str, window: AppFluentWindow) -> None:
        super().__init__(parent = window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "exclusion_list_switch": False,
            "exclusion_list_data": [
                {
                    "markers": "//F[N1]",
                    "info": "游戏文本标记符号",
                    "regex": "//[A-Z]\\[.*?\\]",
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


    # 页面每次展示时触发
    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        # 页面显示时
        self.update_table()

    def update_table(self) -> None:
        # 读取配置文件
        config = self.load_config()
        # 向表格更新数据,只添加新的内容，而不会减项
        TableHelper.update_to_table(self.table, config["exclusion_list_data"], ExclusionListPage.KEYS)


    # 头部
    def add_widget_head(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:

        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("exclusion_list_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["exclusion_list_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "禁翻表",
                (
                "通过构建禁翻表来引导模型，禁止翻译文本中的特殊标记符，占位符，代码段等内容"                   
                + "\n" + "触发机制: 文本含有标记符，或者正则表达式提取生效"
                ),
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
        self.table.setColumnCount(len(ExclusionListPage.KEYS))
        self.table.resizeRowsToContents() # 设置行高度自适应内容
        self.table.resizeColumnsToContents() # 设置列宽度自适应内容
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # 撑满宽度
        self.table.itemChanged.connect(item_changed)

        # 设置水平表头并隐藏垂直表头
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setHorizontalHeaderLabels(
            [
                "标记符",
                "备注",
                "正则",
            ],
        )

        # 向表格更新数据
        TableHelper.update_to_table(self.table, config.get("exclusion_list_data"), ExclusionListPage.KEYS)

    # 底部
    def add_widget_foot(self, parent: QLayout, config: dict, window: AppFluentWindow) -> None:
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)

        # 添加命令
        self.add_command_bar_action_import(self.command_bar_card, config, window)
        self.add_command_bar_action_export(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_add(self.command_bar_card, config, window)
        self.add_command_bar_action_save(self.command_bar_card, config, window)
        self.command_bar_card.add_separator()
        self.add_command_bar_action_reset(self.command_bar_card, config, window)

    # 导入
    def add_command_bar_action_import(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            # 选择文件
            path, _ = QFileDialog.getOpenFileName(None, "选择文件", "", "json 文件 (*.json);;xlsx 文件 (*.xlsx)")
            if not isinstance(path, str) or path == "":
                return

            # 从文件加载数据
            data = TableHelper.load_from_file(path, ExclusionListPage.KEYS)

            # 读取配置文件
            config = self.load_config()
            config["exclusion_list_data"].extend(data)

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config["exclusion_list_data"], ExclusionListPage.KEYS)

            # 从表格加载数据（去重后）
            config["exclusion_list_data"] = TableHelper.load_from_table(self.table, ExclusionListPage.KEYS)

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            self.success_toast("", "数据已导入 ...")

        parent.add_action(
            Action(FluentIcon.DOWNLOAD, "导入", parent, triggered = triggered),
        )

    # 导出
    def add_command_bar_action_export(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            # 加载配置文件
            config = self.load_config()

            # 从表格加载数据
            data = TableHelper.load_from_table(self.table, ExclusionListPage.KEYS)

            # 导出文件
            with open(f"导出_禁翻表.json", "w", encoding = "utf-8") as writer:
                writer.write(json.dumps(data, indent = 4, ensure_ascii = False))

            # 弹出提示
            self.success_toast("", "数据已导出到应用根目录 ...")

        parent.add_action(
            Action(FluentIcon.SHARE, "导出", parent, triggered = triggered),
        )

    # 添加新行
    def add_command_bar_action_add(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            # 添加新行
            self.table.setRowCount(self.table.rowCount() + 1)

            # 弹出提示
            self.success_toast("", "新行已添加 ...")

        parent.add_action(
            Action(FluentIcon.ADD_TO, "添加", parent, triggered = triggered),
        )

    # 保存
    def add_command_bar_action_save(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            # 加载配置文件
            config = self.load_config()

            # 从表格加载数据
            config["exclusion_list_data"] = TableHelper.load_from_table(self.table, ExclusionListPage.KEYS)

            # 清空表格
            self.table.clearContents()

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config["exclusion_list_data"], ExclusionListPage.KEYS)

            # 从表格加载数据（去重后）
            config["exclusion_list_data"] = TableHelper.load_from_table(self.table, ExclusionListPage.KEYS)

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            self.success_toast("", "数据已保存 ...")

        parent.add_action(
            Action(FluentIcon.SAVE, "保存", parent, triggered = triggered),
        )

    # 重置
    def add_command_bar_action_reset(self, parent: CommandBarCard, config: dict, window: AppFluentWindow) -> None:

        def triggered() -> None:
            message_box = MessageBox("警告", "是否确认重置为默认数据 ... ？", window)
            message_box.yesButton.setText("确认")
            message_box.cancelButton.setText("取消")

            if not message_box.exec():
                return

            # 清空表格
            self.table.clearContents()

            # 加载配置文件
            config = self.load_config()

            # 加载默认设置
            config["exclusion_list_data"] = self.default.get("exclusion_list_data")

            # 保存配置文件
            config = self.save_config(config)

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config.get("exclusion_list_data"), ExclusionListPage.KEYS)

            # 弹出提示
            self.success_toast("", "数据已重置 ...")

        parent.add_action(
            Action(FluentIcon.DELETE, "重置", parent, triggered = triggered),
        )