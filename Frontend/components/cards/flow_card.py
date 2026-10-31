from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget, HorizontalSeparator
from qfluentwidgets import FlowLayout
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class FlowCard(CardWidget):

    def __init__(self, title: str, description: str, init = None):
        super().__init__(None)
        
        # 设置容器
        self.setBorderRadius(4)
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        # 添加头部容器
        self.head_container = QFrame(self)
        self.head_hbox = QHBoxLayout(self.head_container)
        self.head_hbox.setSpacing(8)
        self.head_hbox.setContentsMargins(0, 0, 0, 0)
        self.container.addWidget(self.head_container)

        # 添加文本容器
        self.text_container = QFrame(self)
        self.text_vbox = QVBoxLayout(self.text_container)
        self.text_vbox.setSpacing(8)
        self.text_vbox.setContentsMargins(0, 0, 0, 0)
        self.head_hbox.addWidget(self.text_container)

        self.title_label = StrongBodyLabel(title, self)
        self.text_vbox.addWidget(self.title_label)

        self.description_label = CaptionLabel(description, self)
        self.description_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        self.text_vbox.addWidget(self.description_label)

        # 填充
        self.head_hbox.addStretch(1)

        # 添加分割线
        line = HorizontalSeparator()
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

    # 添加控件
    def add_widget(self, widget) -> None:
        self.flow_layout.addWidget(widget)

    # 添加控件到头部
    def add_widget_to_head(self, widget) -> None:
        self.head_hbox.addWidget(widget)

    # 移除所有控件并且删除他们
    def take_all_widgets(self) -> None:
        self.flow_layout.takeAllWidgets()