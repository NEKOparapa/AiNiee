from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QLayout
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import MessageBox
from qfluentwidgets import FluentWindow
from qfluentwidgets import PillPushButton

from Base.Base import Base
from Widget.FlowCard import FlowCard
from Widget.Separator import Separator
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Module_Folders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum

class AdvanceSettingsPage(QFrame, Base):

    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "cn_prompt_toggle": True,
            "prompt_preset": PromptBuilderEnum.COMMON,
            "preserve_line_breaks_toggle": True,
            "preserve_prefix_and_suffix_codes": True,
            "response_conversion_toggle": False,
            "opencc_preset": "s2t",
            "reply_check_switch": {
                "Model Degradation Check": True,
                "Residual Original Text Check": True,
                "Return to Original Text Check": True,
            },
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.vbox = QVBoxLayout(self)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_prompt_language(self.vbox, config, window)
        self.add_widget_prompt_preset(self.vbox, config, window)
        self.vbox.addWidget(Separator())
        self.add_widget_line_breaks(self.vbox, config, window)
        self.add_widget_prefix_and_suffix_codes(self.vbox, config, window)
        self.vbox.addWidget(Separator())
        self.add_widget_opencc(self.vbox, config, window)
        self.add_widget_opencc_preset(self.vbox, config, window)
        self.vbox.addWidget(Separator())
        self.add_widget_result_check(self.vbox, config, window)

        # 填充
        self.vbox.addStretch(1)

    # 中文提示词
    def add_widget_prompt_language(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("cn_prompt_toggle"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["cn_prompt_toggle"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "中文提示词",
                "启用此功能后将使用中文提示词，不启用则使用英文提示词（Sakura 接口无需设置此项）",
                widget_init,
                widget_callback,
            )
        )

    # 提示词预设规则
    def add_widget_prompt_preset(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        items = {
            "通用": PromptBuilderEnum.COMMON,
            "思维链": PromptBuilderEnum.COT,
            "推理模型": PromptBuilderEnum.THINK,
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
                "提示词预设",
                (
                    "通用：综合通用，花费最少，完美破限，兼容各种普通模型"
                    + "\n" + "思维链：即 CoT，融入翻译三步法，提升思考深度，极大增加输出内容，极大增加消耗，完美破限，提升文学质量"
                    + "\n" + "推理模型：精简流程，为 DeepSeek-R1 等推理模型优化，释放推理模型的思考能力，获得最佳翻译质量"
                ),
                items.keys(),
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 保留句内换行符
    def add_widget_line_breaks(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("preserve_line_breaks_toggle"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["preserve_line_breaks_toggle"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "保留句内换行符",
                "启用此功能后，将尝试保留每个句子内的换行符",
                widget_init,
                widget_callback,
            )
        )

    # 保留首尾代码段
    def add_widget_prefix_and_suffix_codes(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("preserve_prefix_and_suffix_codes"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["preserve_prefix_and_suffix_codes"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "保留首尾代码段",
                "启用此功能后，将在翻译前移除每行文本开头和结尾的代码段并在翻译后还原",
                widget_init,
                widget_callback,
            )
        )

    # 自动简繁转换
    def add_widget_opencc(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("response_conversion_toggle"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["response_conversion_toggle"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "自动简繁转换",
                "启用此功能后，在翻译完成时将按照设置的字形映射规则进行简繁转换",
                widget_init,
                widget_callback,
            )
        )

    # 简繁转换预设规则
    def add_widget_opencc_preset(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def init(widget) -> None:
            widget.set_current_index(max(0, widget.find_text(config.get("opencc_preset"))))

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["opencc_preset"] = text
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "简繁转换预设规则",
                "进行简繁转换时的字形预设规则，常用的有：简转繁（s2t）、繁转简（t2s）",
                [
                    "s2t",
                    "s2tw",
                    "s2hk",
                    "s2twp",
                    "t2s",
                    "t2tw",
                    "t2hk",
                    "t2jp",
                    "tw2s",
                    "tw2t",
                    "tw2sp",
                    "hk2s",
                    "hk2t",
                    "jp2t",
                ],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 结果检查
    def add_widget_result_check(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def on_toggled(checked: bool, key) -> None:
            config = self.load_config()
            config["reply_check_switch"][key] = checked
            self.save_config(config)

        def widget_init(widget) -> None:
            pairs = [
                ("模型退化检查", "Model Degradation Check"),
                ("原文返回检查", "Return to Original Text Check"),
                ("翻译残留检查", "Residual Original Text Check"),
            ]

            for v in pairs:
                pill_push_button = PillPushButton(v[0])
                pill_push_button.setContentsMargins(4, 0, 4, 0) # 左、上、右、下
                pill_push_button.setChecked(config["reply_check_switch"].get(v[1]))
                pill_push_button.toggled.connect(lambda checked, key = v[1]: on_toggled(checked, key))
                widget.add_widget(pill_push_button)

        parent.addWidget(
            FlowCard(
                "翻译结果检查",
                "将在翻译结果中检查激活的规则（点亮按钮为激活）：如检测到对应情况，则视为任务执行失败",
                widget_init
            )
        )