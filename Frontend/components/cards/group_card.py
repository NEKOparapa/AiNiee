from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget, HorizontalSeparator
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class GroupCard(CardWidget):

    def __init__(self, title: str, description: str, init = None):
        super().__init__(None)
        
        # 设置容器
        self.setBorderRadius(4)
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        self.title_label = StrongBodyLabel(title, self)
        self.container.addWidget(self.title_label)

        self.description_label = CaptionLabel(description, self)
        self.description_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        self.container.addWidget(self.description_label)

        # 添加分割线
        self.line = HorizontalSeparator(self)
        self.container.addWidget(self.line)

        # 添加流式布局容器
        self.vbox_container = QFrame(self)
        self.vbox = QVBoxLayout(self.vbox_container)
        self.vbox.setSpacing(0)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.container.addWidget(self.vbox_container)

        if init:
            init(self)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_description(self, description: str) -> None:
        self.description_label.setText(description)

    # 添加控件
    def addWidget(self, widget) -> None:
        self.vbox.addWidget(widget)

    # 添加分割线
    def addSeparator(self) -> None:
        line = QFrame(self)
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.vbox.addSpacing(4)
        self.vbox.addWidget(line)
        self.vbox.addSpacing(4)