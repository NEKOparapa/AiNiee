from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import ElevatedCardWidget, ImageLabel
from qfluentwidgets import ComboBox
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel





class TranslationSpeedCard(ElevatedCardWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.vBoxLayout = QVBoxLayout(self) # 垂直布局
        self.vBoxLayout.setAlignment(Qt.AlignCenter) #设置布局的对齐方式为居中对齐。
        self.vBoxLayout.addStretch(1)



        self.caption_label_line = CaptionLabel("速度(行/S)", self)

        self.label_line = StrongBodyLabel('未开始', self)

        self.caption_label_tokens = CaptionLabel("速度(tokens/S)", self)

        self.label_tokens = StrongBodyLabel('未开始', self)


        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.caption_label_line, 0,  Qt.AlignHCenter | Qt.AlignBottom)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.label_line, 0, Qt.AlignHCenter | Qt.AlignBottom)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.caption_label_tokens, 0,  Qt.AlignHCenter | Qt.AlignBottom)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.label_tokens, 0, Qt.AlignHCenter | Qt.AlignBottom)


        self.setFixedSize(168, 176)



    # 设置文本
    def set_text(self, text_line: str, text_tokens: str) -> None:
        self.label_line.setText(text_line)
        self.label_tokens.setText(text_tokens)