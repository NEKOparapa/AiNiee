from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import ElevatedCardWidget, ImageLabel
from qfluentwidgets import ComboBox
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel





class ProjectTypeCard(ElevatedCardWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.vBoxLayout = QVBoxLayout(self) # 垂直布局
        self.vBoxLayout.setAlignment(Qt.AlignCenter) #设置布局的对齐方式为居中对齐。
        self.vBoxLayout.addStretch(1)



        self.caption_label = CaptionLabel("翻译项目", self)

        self.label = StrongBodyLabel('未开始', self)



        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.caption_label, 0,  Qt.AlignHCenter | Qt.AlignBottom)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignHCenter | Qt.AlignBottom)



        self.setFixedSize(168, 176)



    # 设置文本
    def set_text(self, text: str) -> None:
        self.label.setText(text)