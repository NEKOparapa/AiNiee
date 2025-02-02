from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import PlainTextEdit

from Base.Base import Base
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Module_Folders.PromptBuilder.PromptBuilder import PromptBuilder
from Module_Folders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from Module_Folders.PromptBuilder.PromptBuilderThink import PromptBuilderThink

class SystemPromptPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 读取默认提示词
        system_prompt_switch = ""
        with open("./Prompt/think_system.txt", "r", encoding = "utf-8") as reader:
            system_prompt_switch = reader.read().strip()

        # 默认配置
        self.default = {
            "system_prompt_switch": False,
            "system_prompt_content": system_prompt_switch,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 载入配置文件
        config = self.load_config()

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_header(self.container, config)
        self.add_widget_body(self.container, config)
        self.add_widget_footer(self.container, config, window)

    # 头部
    def add_widget_header(self, parent, config) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("system_prompt_switch"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["system_prompt_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "自定义基础指令",
                "启用此功能后，将使用本页中设置的提示词向模型发送请求（不支持 Sakura 模型）",
                widget_init,
                widget_callback,
            )
        )

    # 主体
    def add_widget_body(self, parent, config) -> None:
        self.plain_text_edit = PlainTextEdit(self)
        self.plain_text_edit.setPlainText(config.get("system_prompt_content"))
        parent.addWidget(self.plain_text_edit)

    # 底部
    def add_widget_footer(self, parent, config, window) -> None:
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)

        # 添加命令
        self.add_command_bar_action_01(self.command_bar_card)
        self.add_command_bar_action_02(self.command_bar_card, window)
    # 保存
    def add_command_bar_action_01(self, parent) -> None:
        def callback() -> None:
            # 读取配置文件
            config = self.load_config()

            # 从表格更新数据
            config["system_prompt_content"] = self.plain_text_edit.toPlainText().strip()

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            self.success_toast("", "数据已保存 ...")

        parent.add_action(
            Action(FluentIcon.SAVE, "保存", parent, triggered = callback),
        )

    # 重置
    def add_command_bar_action_02(self, parent, window) -> None:
        def callback():
            message_box = MessageBox("警告", "是否确认重置为默认数据 ... ？", window)
            message_box.yesButton.setText("确认")
            message_box.cancelButton.setText("取消")

            if not message_box.exec():
                return

            # 清空控件
            self.plain_text_edit.setPlainText("")

            # 读取配置文件
            config = self.load_config()

            # 加载默认设置
            config["system_prompt_content"] = self.default.get("system_prompt_content")

            # 保存配置文件
            config = self.save_config(config)

            # 向控件更新数据
            self.plain_text_edit.setPlainText(config.get("system_prompt_content"))

            # 弹出提示
            self.success_toast("", "数据已重置 ...")

        parent.add_action(
            Action(FluentIcon.DELETE, "重置", parent, triggered = callback),
        )