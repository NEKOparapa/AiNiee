from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import LineEdit
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel

class LineEditCard(CardWidget):

    def __init__(self, title: str, description: str, init = None, text_changed = None):
        super().__init__(None)

        # 设置容器
        self.setBorderRadius(4)
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        # 文本控件
        self.vbox_container = QFrame(self)
        self.vbox = QVBoxLayout(self.vbox_container)
        self.vbox.setSpacing(0)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.addWidget(self.vbox_container)

        self.title_label = StrongBodyLabel(title, self)
        self.vbox.addWidget(self.title_label)

        self.description_label = CaptionLabel(description, self)
        self.description_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        self.vbox.addWidget(self.description_label)

        # 填充
        self.hbox.addStretch(1)

        # 添加控件
        self.line_edit = LineEdit()
        self.line_edit.setFixedWidth(192)
        self.line_edit.setClearButtonEnabled(True)
        self.hbox.addWidget(self.line_edit)

        if init:
            init(self)

        if text_changed:
            self.line_edit.textChanged.connect(lambda text: text_changed(self, text))

    # 添加控件
    def add_widget(self, widget) -> None:
        self.hbox.addWidget(widget)

    # 添加间隔
    def add_spacing(self, spacing: int) -> None:
        self.hbox.addSpacing(spacing)

    # 获取文本
    def get_text(self) -> str:
        return self.line_edit.text()

    # 设置文本
    def set_text(self, text: str) -> None:
        self.line_edit.setText(text)

    # 设置输入框宽度
    def set_fixed_width(self, width: int) -> None:
        self.line_edit.setFixedWidth(width)

    # 设置占位符
    def set_placeholder_text(self, text: str) -> None:
        self.line_edit.setPlaceholderText(text)