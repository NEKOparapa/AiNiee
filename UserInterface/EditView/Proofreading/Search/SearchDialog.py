from PyQt5.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import CheckBox, ComboBox, LineEdit, MessageBoxBase

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin


class SearchDialog(ConfigMixin, Base, MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.view = QWidget(self)
        layout = QVBoxLayout(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        self.view.setMinimumWidth(350)

        self.query_edit = LineEdit(self)
        self.query_edit.setPlaceholderText(self.tra("输入搜索内容..."))

        self.flagged_line_checkbox = CheckBox(self.tra("仅搜索被标记行"), self)
        self.regex_checkbox = CheckBox(self.tra("使用正则表达式"), self)

        self.scope_combo = ComboBox(self)
        self.scope_combo.addItems([self.tra("全文"), self.tra("原文"), self.tra("译文")])

        layout.addWidget(self.query_edit)
        layout.addWidget(self.flagged_line_checkbox)
        layout.addWidget(self.regex_checkbox)
        layout.addWidget(self.scope_combo)

        self.viewLayout.addWidget(self.view)

        self.yesButton.setText(self.tra("搜索"))
        self.cancelButton.setText(self.tra("取消"))

        self.search_scopes = {
            self.tra("全文"): "all",
            self.tra("原文"): "source_text",
            self.tra("译文"): "translated_text",
        }
        self.search_query = ""
        self.is_regex = False
        self.search_scope = "all"
        self.is_flagged_search = False

    def accept(self):
        self.search_query = self.query_edit.text()
        self.is_flagged_search = self.flagged_line_checkbox.isChecked()
        self.is_regex = self.regex_checkbox.isChecked()
        self.search_scope = self.search_scopes.get(self.scope_combo.currentText(), "all")
        super().accept()
