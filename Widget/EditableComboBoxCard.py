from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CardWidget
from qfluentwidgets import CaptionLabel
from qfluentwidgets import StrongBodyLabel
from qfluentwidgets import EditableComboBox

class EditableComboBoxCard(CardWidget):

    def __init__(self, title: str, description: str, items: list[str], init = None, current_text_changed = None, current_index_changed = None):
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

        # 下拉框控件
        self.combo_box = EditableComboBox(self)
        self.combo_box.addItems(items)
        self.container.addWidget(self.combo_box)

        if init:
            init(self)

        if current_text_changed:
            self.combo_box.currentTextChanged.connect(lambda text: current_text_changed(self, text))

        if current_index_changed:
            self.combo_box.currentIndexChanged.connect(lambda index: current_index_changed(self, index))

    # 设置列表条目
    def set_items(self, items: list) -> None:
        self.combo_box.clear()
        self.combo_box.addItems(items)

    # 通过文本查找索引
    def find_text(self, text: str) -> int:
        return self.combo_box.findText(text)

    # 获取当前文本
    def get_current_text(self) -> str:
        return self.combo_box.currentText()

    # 设置当前索引
    def set_current_index(self, index) -> None:
        self.combo_box.setCurrentIndex(index)

    # 设置宽度
    def set_fixed_width(self, width:int) -> None:
        self.combo_box.setFixedWidth(width)

    # 设置占位符
    def set_placeholder_text(self, text:str) -> None:
        self.combo_box.setPlaceholderText(text)