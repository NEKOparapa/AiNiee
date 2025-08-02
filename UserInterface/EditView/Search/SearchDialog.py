
from qfluentwidgets import LineEdit, CheckBox, ComboBox, MessageBoxBase
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from Base.Base import Base

class SearchDialog(Base,MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 创建自定义视图
        self.view = QWidget(self)
        layout = QVBoxLayout(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        self.view.setMinimumWidth(350) 
        
        # 创建输入控件
        self.query_edit = LineEdit(self)
        self.query_edit.setPlaceholderText(self.tra("输入搜索内容..."))

        self.flagged_line_checkbox = CheckBox(self.tra("仅搜索被标记行"), self)
        self.regex_checkbox = CheckBox(self.tra("使用正则表达式"), self)
        
        self.scope_combo = ComboBox(self)
        self.scope_combo.addItems([self.tra("全文"), self.tra("原文"), self.tra("译文"), self.tra("润文")])
        
        # 将控件添加到布局中
        layout.addWidget(self.query_edit)
        layout.addWidget(self.flagged_line_checkbox)
        layout.addWidget(self.regex_checkbox)
        layout.addWidget(self.scope_combo)
        
        # 将自定义视图添加到对话框中
        self.viewLayout.addWidget(self.view)
        
        self.yesButton.setText(self.tra("搜索"))
        self.cancelButton.setText(self.tra("取消"))
        
        # 存储搜索参数
        self.search_scopes = {
            self.tra("全文"): "all",
            self.tra("原文"): "source_text",
            self.tra("译文"): "translated_text",
            self.tra("润文"): "polished_text"
        }
        self.search_query = ""
        self.is_regex = False
        self.search_scope = "all"
        self.is_flagged_search = False

    def accept(self):
        """当用户点击"搜索"按钮时，收集数据"""
        self.search_query = self.query_edit.text()
        self.is_flagged_search = self.flagged_line_checkbox.isChecked()
        self.is_regex = self.regex_checkbox.isChecked()
        selected_text = self.scope_combo.currentText()
        self.search_scope = self.search_scopes.get(selected_text, "all")
        
        if not self.search_query:
            pass # 允许空搜索
        
        super().accept()