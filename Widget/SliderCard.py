from PyQt5.Qt import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import Slider
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class SliderCard(CardWidget):

    def __init__(self, title: str, description: str, init = None, value_changed = None):
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
        self.slider = Slider(Qt.Horizontal)
        self.slider.setFixedWidth(256)
        self.slider_value_label = StrongBodyLabel(title, self)
        self.slider_value_label.setFixedWidth(48)
        self.slider_value_label.setAlignment(Qt.AlignCenter)
        self.container.addWidget(self.slider)
        self.container.addWidget(self.slider_value_label)

        if init:
            init(self)

        if value_changed:
            self.slider.valueChanged.connect(lambda value: value_changed(self, value))

    def set_text(self, text:str) -> None:
        self.slider_value_label.setText(text)

    def set_value(self, value: int) -> None:
        self.slider.setValue(value)

    def set_range(self, min: int, max: int) -> None:
        self.slider.setRange(min, max)