from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QHBoxLayout

from qfluentwidgets import SubtitleLabel


class BaseNavigationItem(QWidget):

    def __init__(self, text: str, parent = None):
        super().__init__(parent = parent)

        self.label = SubtitleLabel("", self)
        self.label.setAlignment(Qt.AlignCenter)

        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)

        # 必须给子界面设置全局唯一的对象名
        self.setObjectName(text.replace(' ', '-'))