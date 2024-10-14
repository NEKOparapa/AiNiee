
from PyQt5.Qt import Qt

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import ElevatedCardWidget
from qfluentwidgets import Action
from qfluentwidgets import CommandBar
from qfluentwidgets import FluentIcon

class CommandBarCard(ElevatedCardWidget):

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
        
    # 添加始终隐藏的命令
    def addHiddenAction(self, action: Action):
        self.command_bar.addHiddenAction(action)
        
    # 添加分隔符
    def addSeparator(self):
        self.command_bar.addSeparator()