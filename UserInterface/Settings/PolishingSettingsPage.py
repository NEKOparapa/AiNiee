from PyQt5.QtWidgets import QFrame, QVBoxLayout

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Widget.SpinCard import SpinCard


class PolishingSettingsPage(QFrame, ConfigMixin, Base):
    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "polishing_pre_line_counts": 10,
        }

        config = self.save_config(self.load_config_from_default())

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_pre_lines(self.container, config)
        self.container.addStretch(1)

    def add_widget_pre_lines(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("polishing_pre_line_counts"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["polishing_pre_line_counts"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                self.tra("参考上文行数"),
                self.tra("只影响润色流程的上文参考行数"),
                init=init,
                value_changed=value_changed,
            )
        )
