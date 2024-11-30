import os
import json
from functools import partial

from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import PillPushButton

from Base.Base import Base
from Widget.FlowCard import FlowCard
from Widget.Separator import Separator
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard

class AdvanceSettingsPage(QFrame, Base):

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "cot_toggle": False,
            "cn_prompt_toggle": True,
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
        self.add_widget_01(self.vbox, config)
        self.add_widget_02(self.vbox, config)
        self.vbox.addWidget(Separator())
        self.add_widget_03(self.vbox, config)
        self.add_widget_04(self.vbox, config)
        self.vbox.addWidget(Separator())
        self.add_widget_05(self.vbox, config)
        self.add_widget_06(self.vbox, config)
        self.vbox.addWidget(Separator())
        self.add_widget_07(self.vbox, config)

        # 填充
        self.vbox.addStretch(1)

    # 中文提示词
    def add_widget_01(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("cn_prompt_toggle"))

        def widget_callback(widget, checked: bool):
            config = self.load_config()
            config["cn_prompt_toggle"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "中文提示词",
                "启用此功能后将使用中文提示词，不启用则使用英文提示词（Sakura 模型固定为中文提示词，无需启用此功能）",
                widget_init,
                widget_callback,
            )
        )

    # 思维链模式
    def add_widget_02(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("cot_toggle"))

        def widget_callback(widget, checked: bool):
            config = self.load_config()
            config["cot_toggle"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "思维链模式",
                "思维链（CoT）是一种高级指令模式，在逻辑能力强的模型上可以取得更好的翻译效果，会消耗更多 Token（不支持 Sakura 模型）",
                widget_init,
                widget_callback,
            )
        )

    # 保留句内换行符
    def add_widget_03(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("preserve_line_breaks_toggle"))

        def widget_callback(widget, checked: bool):
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
    def add_widget_04(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("preserve_prefix_and_suffix_codes"))

        def widget_callback(widget, checked: bool):
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
    def add_widget_05(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("response_conversion_toggle"))

        def widget_callback(widget, checked: bool):
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

    # 简繁转换字形映射规则
    def add_widget_06(self, parent, config):
        def init(widget):
            widget.set_current_index(max(0, widget.find_text(config.get("opencc_preset"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["opencc_preset"] = text
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "简繁转换字形映射规则",
                "进行简繁转换时的字形映射规则，常用的有：简转繁（s2t）、繁转简（t2s）",
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

    # 模型退化检查
    def add_widget_07(self, parent, config):

        def on_toggled(checked: bool, key):
            config = self.load_config()
            config["reply_check_switch"][key] = checked
            self.save_config(config)

        def widget_init(widget):
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