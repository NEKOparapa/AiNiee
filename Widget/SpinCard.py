
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import SpinBox
from qfluentwidgets import CardWidget
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class SpinCard(CardWidget):

    def __init__(self, title: str, description: str, init = None, on_value_changed = None):
        super().__init__(None)
        
        # 设置容器
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
        self.container.addStretch(1) # 确保控件顶端对齐
        
        # 微调框控件
        self.spin_box = SpinBox()

        if init:
            init(self.spin_box)

        if on_value_changed:
            self.spin_box.valueChanged.connect(lambda value: on_value_changed(self.spin_box, value))

        self.container.addWidget(self.spin_box)