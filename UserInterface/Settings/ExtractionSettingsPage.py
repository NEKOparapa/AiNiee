from PyQt5.QtWidgets import QFrame, QVBoxLayout

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface.Widget.SpinCard import SpinCard


class ExtractionSettingsPage(QFrame, ConfigMixin, Base):
    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "extract_task_token_limit": 10000,
            "auto_extract_non_translate_switch": False,
        }

        config = self.save_config(self.load_config_from_default())

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_extract_token_limit(self.container, config)
        self.add_widget_auto_extract_non_translate(self.container, config)
        self.container.addStretch(1)

    def add_widget_extract_token_limit(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(1, 9999999)
            widget.set_value(config.get("extract_task_token_limit"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["extract_task_token_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                self.tra("提取任务的 Token 切分数"),
                self.tra("开始翻译中的提取任务会按此 Token 数切分原文"),
                init=init,
                value_changed=value_changed,
            )
        )

    def add_widget_auto_extract_non_translate(self, parent, config) -> None:
        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("auto_extract_non_translate_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["auto_extract_non_translate_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动提取禁翻词条"),
                self.tra("开启该开关后，将自动提取文本中禁止翻译内容，需要用户审查与筛选，避免影响翻译效率"),
                init=init,
                checked_changed=checked_changed,
            )
        )
