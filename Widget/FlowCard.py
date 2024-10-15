
from PyQt5.Qt import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import ElevatedCardWidget
from qfluentwidgets import FlowLayout
from qfluentwidgets import FluentIcon
from qfluentwidgets import PushButton
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class FlowCard(ElevatedCardWidget):

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
        line = QFrame(self)
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.container.addSpacing(4)
        self.container.addWidget(line)
        self.container.addSpacing(4)

        # 添加流式布局容器
        self.flow_container = QFrame(self)
        self.flow_layout = FlowLayout(self.flow_container, needAni = False)
        self.flow_layout.setSpacing(8)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.container.addWidget(self.flow_container)

        if init:
            init(self)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_description(self, description: str) -> None:
        self.description_label.setText(description)

    def set_text(self, text: str) -> None:
        self.push_button.setText(text)

    def set_icon(self, icon: str) -> None:
        self.push_button.setIcon(icon)

    def addWidget(self, widget) -> None:
        self.flow_layout.addWidget(widget)