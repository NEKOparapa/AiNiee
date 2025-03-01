from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import FluentWindow
from qfluentwidgets import PlainTextEdit

from Base.Base import Base
from Widget.CommandBarCard import CommandBarCard
from Widget.ComboBoxCard import ComboBoxCard
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilderThink import PromptBuilderThink

class SystemPromptPage(QFrame, Base):

    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "system_prompt_switch": False,
            "system_prompt_content": PromptBuilder.get_system_default(None),
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
        self.add_widget_header(self.container, config, window)
        self.add_widget_body(self.container, config, window)
        self.add_widget_footer(self.container, config, window)

    # 页面每次展示时触发
    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self.show_event_body(self, event) if callable(getattr(self, "show_event_body", None)) else None

    # 头部
    def add_widget_header(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        items = {
            "通用": PromptBuilderEnum.COMMON,
            "思维链": PromptBuilderEnum.COT,
            "推理模型": PromptBuilderEnum.THINK,
            "自定义提示词": PromptBuilderEnum.CUSTOM,
        }

        def init(widget) -> None:
            prompt_preset = config.get("prompt_preset")

            choice = 0
            for i, v in enumerate(items.values()):
                if v == prompt_preset:
                    choice = i
                    break

            widget.set_current_index(choice)

        def current_text_changed(widget, text: str) -> None:
            choice = self.default.get("prompt_preset")
            for k, v in items.items():
                if k == text:
                    choice = v
                    break

            config = self.load_config()
            config["prompt_preset"] = choice
            self.save_config(config)
            self.success_toast("", "提示词预设规则切换成功，如您在使用自定义提示词功能，建议重置自定义提示词 ...")

        parent.addWidget(
            ComboBoxCard(
                "基础提示词预设",
                (
                    "通用：综合通用，花费最少，兼容各种模型，完美破限"
                    + "\n" + "思维链：即 CoT，融入翻译三步法，提升思考深度，极大增加输出内容，极大增加消耗，提升文学质量，完美破限"
                    + "\n" + "推理模型：精简流程，为 DeepSeek-R1 等推理模型优化，释放推理模型的思考能力，获得最佳翻译质量"
                    + "\n" + "自定义提示词：将使用下方填入的内容作为系统提示词"
                ),
                items.keys(),
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 主体
    def add_widget_body(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def update_widget(widget: QFrame) -> None:
            config = self.load_config()
            self.plain_text_edit.setPlainText(config.get("system_prompt_content"))

        self.plain_text_edit = PlainTextEdit(self)
        self.show_event_body = lambda _, event: update_widget(self.plain_text_edit)
        parent.addWidget(self.plain_text_edit)

    # 底部
    def add_widget_footer(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
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
        def callback() -> None:
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
            if config.get("prompt_preset", PromptBuilderEnum.COMMON) in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT):
                config["system_prompt_content"] = PromptBuilder.get_system_default(config)
            elif config.get("prompt_preset", PromptBuilderEnum.COMMON) == PromptBuilderEnum.THINK:
                config["system_prompt_content"] = PromptBuilderThink.get_system_default(config)
            elif config.get("prompt_preset", PromptBuilderEnum.COMMON) == PromptBuilderEnum.CUSTOM:
                config["system_prompt_content"] = "无内容"

            # 保存配置文件
            config = self.save_config(config)

            # 向控件更新数据
            self.plain_text_edit.setPlainText(config.get("system_prompt_content"))

            # 弹出提示
            self.success_toast("", "数据已重置 ...")

        parent.add_action(
            Action(FluentIcon.DELETE, "重置", parent, triggered = callback),
        )