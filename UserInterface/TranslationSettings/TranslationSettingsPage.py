
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import HorizontalSeparator, PillPushButton

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface.Widget.SpinCard import SpinCard
from UserInterface.Widget.FlowCard import FlowCard



class TranslationSettingsPage(QFrame, ConfigMixin, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "source_language": "auto",
            "target_language": "chinese_simplified",
            "language_filter_switch": False,
            "pre_line_counts": 0,
            "few_shot_and_example_switch": True,
            "auto_process_text_code_segment": False,
            "response_check_switch": {
                "return_to_original_text_check": True,
                "residual_original_text_check": True,
                "newline_character_count_check": True,
                "reply_format_check": False,
            },
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_language_filter(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_pre_lines(self.container, config)
        self.add_auto_process_text_code_segment(self.container, config)
        self.add_widget_few_shot_and_example(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_result_check(self.container, config)

        # 填充
        self.container.addStretch(1)


    # 参考上文行数
    def add_widget_pre_lines(self, parent, config) -> None:
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

    # 非目标语言文本自动过滤
    def add_widget_language_filter(self, parent, config) -> None:

        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("language_filter_switch", True))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["language_filter_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("非目标语言文本自动过滤"),
                self.tra("启用后，将在翻译或润色前自动排除不属于当前目标语言处理范围的文本，仅控制内置 LanguageFilter 功能"),
                init = init,
                checked_changed = checked_changed,
            )
        )


    # 示例模块和预回复模块开关
    def add_widget_few_shot_and_example(self, parent, config) -> None:

        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("few_shot_and_example_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["few_shot_and_example_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("动态示例和预回复功能"),
                self.tra("将在构建整体的翻译提示词时，自动生成动态Few-shot和构建模型预回复内容，不支持本地接口"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 自动预处理
    def add_auto_process_text_code_segment(self, parent, config) -> None:
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

    # 结果检查
    def add_widget_result_check(self, parent, config) -> None:
        def on_toggled(checked: bool, key) -> None:
            config = self.load_config()
            config["response_check_switch"][key] = checked
            self.save_config(config)

        def widget_init(widget) -> None:

            info_cont1 = self.tra("原文返回检查")
            info_cont2 = self.tra("翻译残留检查")
            info_cont3 = self.tra("换行符数检查")
            info_cont4 = self.tra("回复格式强检查") 

            pairs = [
                (info_cont1, "return_to_original_text_check"),
                (info_cont2, "residual_original_text_check"),
                (info_cont3, "newline_character_count_check"),
                (info_cont4, "reply_format_check"),
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
