
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import HorizontalSeparator, PillPushButton

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SpinCard import SpinCard
from Widget.FlowCard import FlowCard



class TranslationSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "source_language": "auto",
            "target_language": "chinese_simplified",
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
        self.add_widget_source_language(self.container, config)
        self.add_widget_target_language(self.container, config)
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

    # 原文语言
    def add_widget_source_language(self, parent, config) -> None:
        # 定义语言与值的配对列表（显示文本, 存储值）
        source_language_pairs = [
            (self.tra("自动检测"), "auto"),
            (self.tra("日语"), "japanese"),
            (self.tra("英语"), "english"),
            (self.tra("韩语"), "korean"),
            (self.tra("俄语"), "russian"),
            (self.tra("德语"), "german"),
            (self.tra("法语"), "french"),
            (self.tra("简中"), "chinese_simplified"),
            (self.tra("繁中"), "chinese_traditional"),
            (self.tra("西班牙语"), "spanish"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in source_language_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("source_language", "auto")

            # 通过值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时存储对应的值"""
            # 通过显示文本查找对应的值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "auto"  # 默认值
            )
            
            config = self.load_config()
            config["source_language"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, _ in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("原文语言"),
                self.tra("设置当前项目所使用的原始文本的语言"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    # 译文语言
    def add_widget_target_language(self, parent, config) -> None:
        # 定义语言与值的配对列表（显示文本, 存储值）
        target_language_pairs = [
            (self.tra("简中"), "chinese_simplified"),
            (self.tra("繁中"), "chinese_traditional"),
            (self.tra("英语"), "english"),
            (self.tra("日语"), "japanese"),
            (self.tra("韩语"), "korean"),
            (self.tra("俄语"), "russian"),
            (self.tra("德语"), "german"),
            (self.tra("法语"), "french"),
            (self.tra("西班牙语"), "spanish"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in target_language_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("target_language", "chinese_simplified")

            # 通过值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时存储对应的值"""
            # 通过显示文本查找对应的值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "chinese_simplified"  # 默认值
            )
            
            config = self.load_config()
            config["target_language"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, _ in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("译文语言"),
                self.tra("设置当前项目所期望的译文文本的语言"),
                options,
                init=init,
                current_text_changed=current_text_changed
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