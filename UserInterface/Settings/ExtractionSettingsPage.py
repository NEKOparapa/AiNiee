from PyQt5.QtWidgets import QFrame, QVBoxLayout

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Widget.SpinCard import SpinCard


class ExtractionSettingsPage(QFrame, ConfigMixin, Base):
    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "extract_task_token_limit": 10000,
        }

        config = self.save_config(self.load_config_from_default())

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_extract_token_limit(self.container, config)
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
