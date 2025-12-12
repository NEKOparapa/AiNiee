from qfluentwidgets import LineEdit
from qfluentwidgets import MessageBoxBase
from qfluentwidgets import StrongBodyLabel

class LineEditMessageBox(MessageBoxBase):

    def __init__(self, window, title:str, message_box_close:callable = None, default_text:str = ""):
        super().__init__(parent = window)

        # 初始化
        self.message_box_close = message_box_close

        # 设置框体
        self.yesButton.setText("确定")
        self.cancelButton.setText("取消")

        # 设置主布局
        self.viewLayout.setContentsMargins(16, 16, 16, 16) # 左、上、右、下

        # 标题
        self.title_label = StrongBodyLabel(title, self)
        self.viewLayout.addWidget(self.title_label)

        # 输入框
        self.line_edit = LineEdit(self)
        self.line_edit.setFixedWidth(256)
        self.line_edit.setClearButtonEnabled(True)
        self.line_edit.setText(default_text)
        self.viewLayout.addWidget(self.line_edit)

    # 重写验证方法
    def validate(self):
        if self.line_edit.text().strip() != "":
            if self.message_box_close:
                self.message_box_close(self, self.line_edit.text())

            return True

    # 设置提示文本
    def set_placeholder_text(self, text: str) -> None:
        self.line_edit.setPlaceholderText(text)