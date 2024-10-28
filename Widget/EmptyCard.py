from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import PushButton
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class EmptyCard(CardWidget):

    def __init__(self, title: str, description: str, init = None, clicked = None):
        super().__init__(None)

        # 设置容器
        self.setBorderRadius(4)
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        # 文本控件
        self.vbox = QVBoxLayout()

        self.title_label = StrongBodyLabel(title, self)
        self.description_label = CaptionLabel(description, self)
        self.description_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))

        self.vbox.addWidget(self.title_label)
        self.vbox.addWidget(self.description_label)
        self.hbox.addLayout(self.vbox)

        # 填充
        self.hbox.addStretch(1)

        if init:
            init(self)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_description(self, description: str) -> None:
        self.description_label.setText(description)

    def add_widget(self, widget) -> None:
        self.hbox.addWidget(widget)

    def add_spacing(self, space: int) -> None:
        self.hbox.addSpacing(space)