from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class Separator(QWidget):

    def __init__(self):
        super().__init__(None)
        
        # 设置容器
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(4, 8, 4, 8) # 左、上、右、下

        # 添加分割线
        line = QWidget(self)
        line.setFixedHeight(1)
        line.setStyleSheet("QWidget { background-color: #C0C0C0; }")
        self.vbox.addWidget(line)
