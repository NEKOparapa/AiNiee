from PyQt5.QtWidgets import QFrame, QVBoxLayout
from qfluentwidgets import Action, FluentIcon, MessageBox, PlainTextEdit

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Widget.CommandBarCard import CommandBarCard
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface.Widget.Toast import ToastMixin


class WorldBuildingPromptPage(QFrame, ConfigMixin, ToastMixin, Base):
    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.default = {
            "world_building_switch": False,
            "world_building_content": "故事发生在魔法世界，到三十岁还保持童真，就可以学会大火球魔法，成为魔法师。",
        }

        config = self.save_config(self.load_config_from_default())

        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        self.add_widget_header(self.container, config)
        self.add_widget_body(self.container, config)
        self.add_widget_footer(self.container, window)

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
                self.tra("启用此功能后，将根据本页中设置的内容构建背景设定提示，并补充到基础提示词中（不支持本地类模型）"),
                widget_init,
                widget_callback,
            )
        )

    def add_widget_body(self, parent, config):
        self.plain_text_edit = PlainTextEdit(self)
        self.plain_text_edit.setPlainText(config.get("world_building_content"))
        parent.addWidget(self.plain_text_edit)

    def add_widget_footer(self, parent, window):
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)
        self.add_command_bar_action_save(self.command_bar_card)
        self.add_command_bar_action_reset(self.command_bar_card, window)

    def add_command_bar_action_save(self, parent):
        def callback():
            config = self.load_config()
            config["world_building_content"] = self.plain_text_edit.toPlainText().strip()
            self.save_config(config)
            self.success_toast("", self.tra("数据已保存") + " ...")

        parent.add_action(Action(FluentIcon.SAVE, self.tra("保存"), parent, triggered=callback))

    def add_command_bar_action_reset(self, parent, window):
        def callback():
            message_box = MessageBox("Warning", self.tra("是否确认重置为默认数据") + " ... ？", window)
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))
            if not message_box.exec():
                return

            self.plain_text_edit.setPlainText("")
            config = self.load_config()
            config["world_building_content"] = self.default.get("world_building_content")
            self.save_config(config)
            self.plain_text_edit.setPlainText(config.get("world_building_content"))
            self.success_toast("", self.tra("数据已重置") + " ... ")

        parent.add_action(Action(FluentIcon.DELETE, self.tra("重置"), parent, triggered=callback))
