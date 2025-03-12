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
            "prompt_preset":PromptBuilderEnum.COMMON,
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
        # 定义预设配对列表（显示文本, 存储值）
        preset_pairs = [
            (self.tra("通用"), PromptBuilderEnum.COMMON),
            (self.tra("思维链"), PromptBuilderEnum.COT),
            (self.tra("推理模型"), PromptBuilderEnum.THINK),
            (self.tra("自定义提示词"), PromptBuilderEnum.CUSTOM),
        ]

        # 生成翻译后的显示文本列表
        options = [display for display, _ in preset_pairs]

        def init(widget) -> None:
            """根据存储的枚举值设置当前选项"""
            current_value = config.get("prompt_preset", self.default["prompt_preset"])
            # 通过枚举值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(preset_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """根据显示文本查找对应的枚举值"""
            value = next(
                (value for display, value in preset_pairs if display == text),
                self.default["prompt_preset"]  # 默认值
            )
            
            config = self.load_config()
            config["prompt_preset"] = value
            self.save_config(config)
            info_cont = self.tra("提示词预设规则切换成功") + " ..."
            self.success_toast("", info_cont)

        # 构建多语言描述（保持原有翻译方式）
        info_cont1 = self.tra("通用：综合通用，花费最少，兼容各种模型，完美破限") 
        info_cont2 = self.tra("思维链：融入翻译三步法，提升思考深度，极大增加输出内容，极大增加消耗，提升文学质量，适合普通模型，完美破限")
        info_cont3 = self.tra("推理模型：精简流程，为 DeepSeek-R1 等推理模型优化，释放推理模型的思考能力，获得最佳翻译质量")
        info_cont4 = self.tra("自定义提示词：将使用下方填入的内容作为系统提示词")

        parent.addWidget(
            ComboBoxCard(
                self.tra("基础提示词预设"),
                "\n".join([info_cont1, info_cont2, info_cont3, info_cont4]),
                options,
                init=init,
                current_text_changed=current_text_changed
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
            info_cont = self.tra("数据已保存") + " ..."
            self.success_toast("", info_cont)


        parent.add_action(
            Action(FluentIcon.SAVE, self.tra("保存"), parent, triggered = callback),
        )

    # 重置
    def add_command_bar_action_02(self, parent, window) -> None:
        def callback() -> None:
            info_cont1 = self.tra("是否确认重置为默认数据")  + " ... ？"
            message_box = MessageBox("Warning", info_cont1, window)
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))

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
                config["system_prompt_content"] = "NONE"

            # 保存配置文件
            config = self.save_config(config)

            # 向控件更新数据
            self.plain_text_edit.setPlainText(config.get("system_prompt_content"))

            # 弹出提示
            info_cont2 = self.tra("数据已重置")  + " ... "
            self.success_toast("", info_cont2)

        parent.add_action(
            Action(FluentIcon.DELETE,self.tra("重置"), parent, triggered = callback),
        )