from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import ComboBox
from qfluentwidgets import CardWidget
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class ComboBoxCard(CardWidget):

    def __init__(self, title: str, description: str, items: list[str], init = None, on_current_index_changed = None):
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
        
        # 下拉框控件
        self.combo_box = ComboBox()
        self.combo_box.addItems(items)

        if init:
            init(self.combo_box)

        if on_current_index_changed:
            self.combo_box.currentIndexChanged.connect(lambda index: on_current_index_changed(self.combo_box, index))

        self.container.addWidget(self.combo_box)
