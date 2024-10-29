from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import PushButton
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class PushButtonCard(CardWidget):

    def __init__(self, title: str, description: str, init = None, clicked = None):
        super().__init__(None)

        # 设置容器
        self.setBorderRadius(4)
        self.container = QHBoxLayout(self)
        self.container.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        # 文本控件
        self.vbox = QVBoxLayout()

        self.title_label = StrongBodyLabel(title, self)
        self.description_label = CaptionLabel(description, self)
        self.description_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))

        self.vbox.addWidget(self.title_label)
        self.vbox.addWidget(self.description_label)
        self.container.addLayout(self.vbox)

        # 填充
        self.container.addStretch(1)

        # 添加控件
        self.push_button = PushButton("", self)
        self.container.addWidget(self.push_button)

        if init:
            init(self)

        if clicked:
            self.push_button.clicked.connect(lambda value: clicked(self))

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_description(self, description: str) -> None:
        self.description_label.setText(description)

    def set_text(self, text: str) -> None:
        self.push_button.setText(text)

    def set_icon(self, icon: str) -> None:
        self.push_button.setIcon(icon)