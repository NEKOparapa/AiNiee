from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QVBoxLayout, QWidget
from PyQt5.QtCore import pyqtSignal

from qfluentwidgets import CardWidget, CaptionLabel, LineEdit, MessageBoxBase, PushButton, StrongBodyLabel, EditableComboBox, SubtitleLabel,FluentIcon, ToolButton



class EditableComboBoxCard(CardWidget):
    items_changed = pyqtSignal(list)  # 添加一个信号，用于通知外部选项列表已更改

    def __init__(self, title: str, description: str, items: list[str], init = None, current_text_changed = None, current_index_changed = None):
        super().__init__(None)

        self._items = items.copy()  # 存储原始 items 列表，用于弹出窗口编辑
        # 设置容器
        self.setBorderRadius(4)
        self.container = QHBoxLayout(self)
        self.container.setContentsMargins(16, 16, 16, 16)  # 左、上、右、下

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
        self.set_items(items) # 使用 set_items 初始化，确保 _items 被正确设置
        self.container.addWidget(self.combo_box)

        # 编辑按钮
        self.edit_button = ToolButton(FluentIcon.EDIT, self)
        self.edit_button.clicked.connect(self._show_edit_items_popup) # 连接按钮点击事件到弹出窗口函数
        self.container.addWidget(self.edit_button)


        if init:
            init(self)

        if current_text_changed:
            self.combo_box.currentTextChanged.connect(lambda text: current_text_changed(self, text))

        if current_index_changed:
            self.combo_box.currentIndexChanged.connect(lambda index: current_index_changed(self, index))

    # 设置列表条目
    def set_items(self, items: list) -> None:
        self._items = items.copy() # 更新内部存储的 items 列表
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
    def set_fixed_width(self, width: int) -> None:
        self.combo_box.setFixedWidth(width)

    # 设置占位符
    def set_placeholder_text(self, text: str) -> None:
        self.combo_box.setPlaceholderText(text)

    # 显示编辑模型框
    def _show_edit_items_popup(self):
        dialog = EditItemsMessageBox(self._items, self.window())  # 使用顶层窗口作为parent，否则位置错乱
        if dialog.exec_():
            new_items = dialog.get_items()
            if new_items:
                self.set_items(new_items)
                self.items_changed.emit(new_items)



class EditItemsMessageBox(MessageBoxBase):
    """自定义消息框，用于编辑选项"""

    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('编辑选项', self)
        self.viewLayout.addWidget(self.titleLabel)

        # 创建垂直布局用于存放所有选项行
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(0)  # 设置控件之间的固定间距为0像素
        self.rows_layout.setContentsMargins(0, 0, 0, 0)  # 设置布局的边距为0
        self.viewLayout.addLayout(self.rows_layout)

        # 初始化添加现有选项
        for item in items:
            self._add_row(item)

        # 添加“新增”按钮
        self.add_button = PushButton('添加', self)
        self.add_button.clicked.connect(self._add_new_row)
        self.viewLayout.addWidget(self.add_button)

        # 设置对话框最小宽度
        self.widget.setMinimumWidth(450)

    def _add_row(self, text=''):
        """添加单行（输入框+删除按钮）"""
        row_widget = QWidget()
        h_layout = QHBoxLayout(row_widget)

        # 输入框
        line_edit = LineEdit(row_widget)
        line_edit.setText(text)

        # 删除按钮
        delete_btn = ToolButton(FluentIcon.DELETE, row_widget)
        delete_btn.clicked.connect(lambda: self._delete_row(row_widget))

        # 将控件加入布局
        h_layout.addWidget(line_edit, 1)  # 输入框扩展填充
        h_layout.addWidget(delete_btn)

        self.rows_layout.addWidget(row_widget)

    def _delete_row(self, row_widget):
        """删除指定行"""
        self.rows_layout.removeWidget(row_widget)
        row_widget.deleteLater()

    def _add_new_row(self):
        """添加新空行"""
        self._add_row('')

    def get_items(self) -> list[str]:
        """获取所有非空选项（自动去除首尾空格）"""
        items = []
        for i in range(self.rows_layout.count()):
            row_widget = self.rows_layout.itemAt(i).widget()
            if row_widget:
                line_edit = row_widget.findChild(LineEdit)
                if line_edit:
                    text = line_edit.text().strip()
                    if text:  # 检查文本是否非空，防止用户空添加
                        items.append(text)
        return items