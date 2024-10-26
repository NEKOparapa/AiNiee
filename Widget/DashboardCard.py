from PyQt5.Qt import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QHBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import SubtitleLabel
from qfluentwidgets import LargeTitleLabel
from qfluentwidgets import StrongBodyLabel

class DashboardCard(CardWidget):

    def __init__(self, title: str, value: str, unit: str, init = None, clicked = None):
        super().__init__(None)
        
        # 设置容器
        self.setBorderRadius(4)
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        self.title_label = SubtitleLabel(title, self)
        self.container.addWidget(self.title_label)

        # 添加分割线
        line = QWidget(self)
        line.setFixedHeight(1)
        line.setStyleSheet("QWidget { background-color: #C0C0C0; }")
        self.container.addSpacing(4)
        self.container.addWidget(line)
        self.container.addSpacing(4)

        # 添加控件
        self.body_hbox_container = QWidget(self)
        self.body_hbox = QHBoxLayout(self.body_hbox_container)
        self.body_hbox.setSpacing(0)
        self.body_hbox.setContentsMargins(0, 0, 0, 0)

        self.unit_vbox_container = QWidget(self)
        self.unit_vbox = QVBoxLayout(self.unit_vbox_container)
        self.unit_vbox.setSpacing(0)
        self.unit_vbox.setContentsMargins(0, 0, 0, 0)

        self.unit_label = StrongBodyLabel(unit, self)
        self.unit_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.unit_vbox.addSpacing(20)
        self.unit_vbox.addWidget(self.unit_label)
        
        self.value_label = LargeTitleLabel(value, self)
        self.value_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        
        self.body_hbox.addStretch(1)
        self.body_hbox.addWidget(self.value_label, 1)
        self.body_hbox.addSpacing(6)
        self.body_hbox.addWidget(self.unit_vbox_container)
        self.body_hbox.addStretch(1)
        self.container.addWidget(self.body_hbox_container, 1)

        if init:
            init(self)

    def set_unit(self, unit: str):
        self.unit_label.setText(unit)

    def set_value(self, value: str):
        self.value_label.setText(value)