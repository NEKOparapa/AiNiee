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
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum

class AdvanceSettingsPage(QFrame, Base):

    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "auto_glossary_toggle": False,
            "auto_exclusion_list_toggle": False,
            "auto_process_text_code_segment": False,
            "response_conversion_toggle": False,
            "opencc_preset": "s2t",
            "response_check_switch": {
                "model_degradation_check": True,
                "return_to_original_text_check": True,
                "residual_original_text_check": True,
            },
        }

        # 载入用户配置合并类默认配置，并重新保存配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.vbox = QVBoxLayout(self)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_auto_glossary(self.vbox, config, window)
        self.add_widget_auto_exclusion_list(self.vbox, config, window)
        self.vbox.addWidget(Separator())
        self.add_auto_process_text_code_segment(self.vbox, config, window)
        self.vbox.addWidget(Separator())
        self.add_widget_opencc(self.vbox, config, window)
        self.add_widget_opencc_preset(self.vbox, config, window)
        self.vbox.addWidget(Separator())
        self.add_widget_result_check(self.vbox, config, window)

        # 填充
        self.vbox.addStretch(1)


    # 自动术语表
    def add_widget_auto_glossary(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        # 初始化控件状态
        def widget_init(widget) -> None:
            widget.set_checked(config.get("auto_glossary_toggle"))
        # 监控控件变化，更新配置并保存
        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_glossary_toggle"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("AI构建术语表"),
                self.tra(
                "将由AI辅助生成术语表，自动录入，自动应用到后续翻译任务\n开启该功能会增加模型负担，建议在强力模型上开启，不支持本地类接口"
                ),
                widget_init,
                widget_callback,
            )
        )


    # 自动禁翻表
    def add_widget_auto_exclusion_list(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("auto_exclusion_list_toggle"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_exclusion_list_toggle"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("AI构建禁翻表"),
                self.tra(
                "将由AI辅助生成禁翻表，自动录入，暂不应用到后续翻译任务\n开启该功能会增加模型负担，建议在推理模型上开启，不支持本地类接口\n建议在翻译游戏内嵌文本时开启，提取内容有时存在问题，需要手动检查过滤"
                ),
                widget_init,
                widget_callback,
            )
        )



    # 保留首尾代码段
    def add_auto_process_text_code_segment(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("auto_process_text_code_segment"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_process_text_code_segment"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动处理文本代码段"),
                self.tra(
                "启用此功能后，联动正则库与禁翻表，将在翻译前移除首尾的代码段，占位中间的代码段，并在翻译后还原"
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

            info_cont1 = self.tra("模型退化检查")
            info_cont2 = self.tra("原文返回检查")
            info_cont3 = self.tra("翻译残留检查")

            pairs = [
                (info_cont1, "model_degradation_check"),
                (info_cont2, "return_to_original_text_check"),
                (info_cont3, "residual_original_text_check"),
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