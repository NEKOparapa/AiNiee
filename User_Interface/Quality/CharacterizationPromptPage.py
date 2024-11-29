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
from Module_Folders.TableHelper import TableHelper
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard
from User_Interface import AppFluentWindow

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

    def __init__(self, text: str, window: AppFluentWindow) -> None:
        super().__init__(parent = window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
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
            widget.set_checked(config.get("characterization_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["characterization_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "自定义角色介绍",
                "启用此功能后，将根据本页中设置的信息构建提示词向模型发送请求，仅在逻辑能力强的模型上有效（不支持 Sakura 模型）",
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
        self.table.setColumnCount(len(CharacterizationPromptPage.KEYS))
        self.table.resizeRowsToContents() # 设置行高度自适应内容
        self.table.resizeColumnsToContents() # 设置列宽度自适应内容
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # 撑满宽度
        self.table.itemChanged.connect(item_changed)

        # 设置水平表头并隐藏垂直表头
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setHorizontalHeaderLabels([
            "原名",
            "译名",
            "性别",
            "年龄",
            "性格",
            "说话风格",
            "补充信息",
        ])

        # 向表格更新数据
        TableHelper.update_to_table(self.table, config.get("characterization_data"), CharacterizationPromptPage.KEYS)

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
            data = TableHelper.load_from_file(path, CharacterizationPromptPage.KEYS)

            # 读取配置文件
            config = self.load_config()
            config["characterization_data"].extend(data)

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config["characterization_data"], CharacterizationPromptPage.KEYS)

            # 从表格加载数据（去重后）
            config["characterization_data"] = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)

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
            data = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)

            # 导出文件
            with open(f"导出_角色介绍.json", "w", encoding = "utf-8") as writer:
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
            config["characterization_data"] = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)

            # 清空表格
            self.table.clearContents()

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config["characterization_data"], CharacterizationPromptPage.KEYS)

            # 从表格加载数据（去重后）
            config["characterization_data"] = TableHelper.load_from_table(self.table, CharacterizationPromptPage.KEYS)

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
            config["characterization_data"] = self.default.get("characterization_data")

            # 保存配置文件
            config = self.save_config(config)

            # 向表格更新数据
            TableHelper.update_to_table(self.table, config.get("characterization_data"), CharacterizationPromptPage.KEYS)

            # 弹出提示
            self.success_toast("", "数据已重置 ...")

        parent.add_action(
            Action(FluentIcon.DELETE, "重置", parent, triggered = triggered),
        )