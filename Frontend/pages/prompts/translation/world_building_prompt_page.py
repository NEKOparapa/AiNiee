from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, MessageBox, PlainTextEdit, StrongBodyLabel, ToolButton

from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin
from Frontend.components.cards.switch_button_card import SwitchButtonCard
from Frontend.components.toast import ToastMixin


class WorldBuildingPromptPage(QFrame, ConfigMixin, ToastMixin, Base):
    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = self.get_default_section("WorldBuildingPromptPage")

        config = self.initialize_config()

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_header(self.container, config)
        self.add_widget_body(self.container, config)

    def add_widget_header(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("world_building_switch"))

        def widget_callback(widget, checked: bool):
            current_config = self.load_config()
            current_config["world_building_switch"] = checked
            self.save_config(current_config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自定义背景设定"),
                self.tra("启用此功能后，将根据本页中设置的内容构建背景设定提示，并补充到基础提示词中"),
                widget_init,
                widget_callback,
            )
        )

    def add_widget_body(self, parent, config):
        parent.addWidget(self._create_action_toolbar())

        self.plain_text_edit = PlainTextEdit(self)
        self.plain_text_edit.setPlainText(config.get("world_building_content", ""))
        parent.addWidget(self.plain_text_edit)

    def _create_action_toolbar(self) -> QWidget:
        toolbar_widget = QWidget(self)
        layout = QHBoxLayout(toolbar_widget)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(StrongBodyLabel(self.tra("背景内容"), self))
        layout.addStretch(1)

        save_button = ToolButton(FluentIcon.SAVE, self)
        save_button.setToolTip(self.tra("保存"))
        save_button.clicked.connect(self.save_data)
        layout.addWidget(save_button)

        reset_button = ToolButton(FluentIcon.DELETE, self)
        reset_button.setToolTip(self.tra("重置"))
        reset_button.clicked.connect(self.reset_data)
        layout.addWidget(reset_button)

        return toolbar_widget

    def save_data(self):
        config = self.load_config()
        config["world_building_content"] = self.plain_text_edit.toPlainText().strip()
        self.save_config(config)
        self.success_toast("", self.tra("数据已保存") + " ...")

    def reset_data(self):
        message_box = MessageBox(self.tra("警告"), self.tra("是否确认重置为默认数据?") + " ... ？", self.window())
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))
        if not message_box.exec():
            return

        config = self.load_config()
        config["world_building_content"] = self.default.get("world_building_content", "")
        self.save_config(config)
        self.plain_text_edit.setPlainText(config.get("world_building_content", ""))
        self.success_toast("", self.tra("数据已重置") + " ... ")
