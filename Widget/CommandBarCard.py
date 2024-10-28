from PyQt5.Qt import Qt
from PyQt5.QtWidgets import QHBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import Action
from qfluentwidgets import CommandBar

class CommandBarCard(CardWidget):

    def __init__(self, ):
        super().__init__(None)

        # 设置容器
        self.setBorderRadius(4)
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        # 文本控件
        self.command_bar = CommandBar()
        self.command_bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.hbox.addWidget(self.command_bar)

    def add_widget(self, widget):
        return self.hbox.addWidget(widget)

    def add_stretch(self, stretch: int):
        self.hbox.addStretch(stretch)

    def add_spacing(self, spacing: int):
        self.hbox.addSpacing(spacing)

    def add_action(self, action: Action):
        return self.command_bar.addAction(action)

    def add_separator(self):
        self.command_bar.addSeparator()

    def set_minimum_width(self, min_width: int):
        self.command_bar.setMinimumWidth(min_width)