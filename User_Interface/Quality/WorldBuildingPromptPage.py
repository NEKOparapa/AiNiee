from PyQt5.Qt import Qt
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import InfoBar
from qfluentwidgets import InfoBarPosition
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import PlainTextEdit

from AiNieeBase import AiNieeBase
from Widget.CommandBarCard import CommandBarCard
from Widget.SwitchButtonCard import SwitchButtonCard

class WorldBuildingPromptPage(QFrame, AiNieeBase):

    DEFAULT = {
        "world_building_switch": False,
        "world_building_content": (
            "故事发生在魔法世界，到三十岁还保持童真，就可以学会大火球魔法，成为魔法师。"
        ),
    }

    def __init__(self, text: str, parent):
        QFrame.__init__(self, parent)
        AiNieeBase.__init__(self)
        self.setObjectName(text.replace(" ", "-"))

        # 载入配置文件
        config = self.load_config()

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_header(self.container, config)
        self.add_widget_body(self.container, config)
        self.add_widget_footer(self.container, config, parent)

    # 头部
    def add_widget_header(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("world_building_switch"))
            
        def widget_callback(widget, checked: bool):
            config = self.load_config()
            config["world_building_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "自定义世界观设定", 
                "启用此功能后，将根据本页中设置的信息构建提示词向模型发送请求，建议在逻辑能力强的模型上启用（不支持 Sakura 模型）",
                widget_init,
                widget_callback,
            )
        )

    # 主体
    def add_widget_body(self, parent, config):
        self.plain_text_edit = PlainTextEdit(self)
        self.plain_text_edit.setPlainText(config.get("world_building_content"))
        parent.addWidget(self.plain_text_edit)

    # 底部
    def add_widget_footer(self, parent, config, window):
        self.command_bar_card = CommandBarCard()
        parent.addWidget(self.command_bar_card)
        
        # 添加命令
        self.add_command_bar_action_01(self.command_bar_card)
        self.add_command_bar_action_02(self.command_bar_card, window)
    # 保存
    def add_command_bar_action_01(self, parent):
        def callback():
            # 读取配置文件
            config = self.load_config()

            # 从表格更新数据
            config["world_building_content"] = self.plain_text_edit.toPlainText().strip()

            # 保存配置文件
            config = self.save_config(config)

            # 弹出提示
            InfoBar.success(
                title = "",
                content = "数据已保存 ...",
                parent = self,
                duration = 2000,
                orient = Qt.Horizontal,
                position = InfoBarPosition.TOP,
                isClosable = True,
            )

        parent.addAction(
            Action(FluentIcon.SAVE, "保存", parent, triggered = callback),
        )
        
    # 重置
    def add_command_bar_action_02(self, parent, window):
        def callback():
            message_box = MessageBox("警告", "是否确认重置为默认数据 ... ？", window)
            message_box.yesButton.setText("确认")
            message_box.cancelButton.setText("取消")

            if not message_box.exec():
                return

            # 清空控件
            self.plain_text_edit.setPlainText("")

            # 读取配置文件
            config = self.load_config()

            # 加载默认设置
            for k, v in self.DEFAULT.items():
                config[k] = v

            # 加载默认设置
            config["world_building_content"] = self.DEFAULT.get("world_building_content")

            # 向控件更新数据
            self.plain_text_edit.setPlainText(config.get("world_building_content"))

            # 弹出提示
            InfoBar.success(
                title = "",
                content = "数据已重置 ...",
                parent = self,
                duration = 2000,
                orient = Qt.Horizontal,
                position = InfoBarPosition.TOP,
                isClosable = True,
            )

        parent.addAction(
            Action(FluentIcon.DELETE, "重置", parent, triggered = callback),
        )