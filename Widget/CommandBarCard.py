from PyQt5.Qt import Qt
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import Action
from qfluentwidgets import CommandBar

class CommandBarCard(CardWidget):

    def __init__(self, ):
        super().__init__(None)
        
        # 设置容器
        self.setBorderRadius(4)
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        # 文本控件
        self.command_bar = CommandBar()
        self.command_bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.container.addWidget(self.command_bar)

    # 添加命令
    def addAction(self, action: Action):
        self.command_bar.addAction(action)
        
    # 添加分隔符
    def addSeparator(self):
        self.command_bar.addSeparator()

    # 添加命令
    def add_action(self, action: Action):
        return self.command_bar.addAction(action)

    # 添加分隔符
    def add_separator(self):
        self.command_bar.addSeparator()