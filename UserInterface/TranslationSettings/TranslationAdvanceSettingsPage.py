from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QLayout
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import FluentWindow, HorizontalSeparator
from qfluentwidgets import PillPushButton

from Base.Base import Base
from Widget.SpinCard import SpinCard
from Widget.FlowCard import FlowCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard

class TranslationAdvanceSettingsPage(QFrame, Base):

    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "pre_line_counts": 0,
            "few_shot_and_example_switch": True,
            "auto_process_text_code_segment": False,
            "response_conversion_toggle": False,
            "opencc_preset": "s2t",
            "response_check_switch": {
                "return_to_original_text_check": True,
                "residual_original_text_check": True,
                "newline_character_count_check": True,
            },
        }

        # 载入用户配置合并类默认配置，并重新保存配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.vbox = QVBoxLayout(self)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_05(self.vbox, config)
        self.add_widget_few_shot_and_example(self.vbox, config, window)
        self.vbox.addWidget(HorizontalSeparator())
        self.add_auto_process_text_code_segment(self.vbox, config, window)
        self.vbox.addWidget(HorizontalSeparator())
        self.add_widget_opencc(self.vbox, config, window)
        self.add_widget_opencc_preset(self.vbox, config, window)
        self.vbox.addWidget(HorizontalSeparator())
        self.add_widget_result_check(self.vbox, config, window)

        # 填充
        self.vbox.addStretch(1)

    # 每个子任务携带的参考上文行数
    def add_widget_05(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("pre_line_counts"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["pre_line_counts"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                self.tra("参考上文行数"),
                self.tra("行数不宜设置过大，建议10行以内 (不支持本地类接口)"),
                init = init,
                value_changed = value_changed,
            )
        )

    # 示例模块和预回复模块开关
    def add_widget_few_shot_and_example(self, parent: QLayout, config: dict, window: FluentWindow) -> None:

        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("few_shot_and_example_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["few_shot_and_example_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("动态示例和预回复功能"),
                self.tra("启用此功能后，将在构建整体的翻译提示词时，自动生成动态Few-shot和构建模型预回复内容，不支持本地接口"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 自动预处理
    def add_auto_process_text_code_segment(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("auto_process_text_code_segment"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_process_text_code_segment"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动预处理文本"),
                self.tra(
                "启用此功能后，根据正则库与禁翻表，将在翻译前移除文本首尾的非翻译内容，占位文本中间的非翻译内容，并在翻译后还原"
                ),
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
                self.tra("自动简繁转换"),
                self.tra("启用此功能后，在翻译完成时将按照设置的字形映射规则进行简繁转换"),
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
                self.tra("简繁转换预设规则"),
                self.tra("进行简繁转换时的字形预设规则，常用的有：简转繁（s2t）、繁转简（t2s）"),
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
            config["response_check_switch"][key] = checked
            self.save_config(config)

        def widget_init(widget) -> None:

            info_cont1 = self.tra("原文返回检查")
            info_cont2 = self.tra("翻译残留检查")
            info_cont3 = self.tra("换行符数检查")

            pairs = [
                (info_cont1, "return_to_original_text_check"),
                (info_cont2, "residual_original_text_check"),
                (info_cont3, "newline_character_count_check"),
            ]

            for v in pairs:
                pill_push_button = PillPushButton(v[0])
                pill_push_button.setContentsMargins(4, 0, 4, 0) # 左、上、右、下
                pill_push_button.setChecked(config["response_check_switch"].get(v[1]))
                pill_push_button.toggled.connect(lambda checked, key = v[1]: on_toggled(checked, key))
                widget.add_widget(pill_push_button)

        parent.addWidget(
            FlowCard(
                self.tra("翻译结果检查"),
                self.tra("将在翻译结果中检查激活的规则（点亮按钮为激活）：如检测到对应情况，则视为任务执行失败"),
                widget_init
            )
        )