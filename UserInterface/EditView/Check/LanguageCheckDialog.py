from qfluentwidgets import ComboBox, CheckBox, MessageBoxBase
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from Base.Base import Base

class LanguageCheckDialog(Base, MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 创建自定义视图
        self.view = QWidget(self)
        layout = QVBoxLayout(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        self.view.setMinimumWidth(350)

        # 创建复选框
        self.polish_checkbox = CheckBox(self.tra("润文"), self)
        self.translate_checkbox = CheckBox(self.tra("译文"), self)
        
        # 创建下拉菜单
        self.mode_combo = ComboBox(self)
        self.mode_combo.addItems([self.tra("宏观统计"), self.tra("精准判断")])
        
        # 将控件添加到布局中
        layout.addWidget(self.polish_checkbox)
        layout.addWidget(self.translate_checkbox)
        layout.addWidget(self.mode_combo)
        
        
        self.viewLayout.addWidget(self.view)
        
        self.yesButton.setText(self.tra("检查"))
        self.cancelButton.setText(self.tra("取消"))

        # 默认选择
        self.translate_checkbox.setChecked(True)
        self.polish_checkbox.setEnabled(False)
        
        # 存储最终的检查模式
        self.check_mode = ""

        # 连接信号，实现复选框的互斥逻辑
        self.polish_checkbox.stateChanged.connect(self._on_checkbox_changed)
        self.translate_checkbox.stateChanged.connect(self._on_checkbox_changed)

    def _on_checkbox_changed(self, state):
        sender = self.sender()
        if state:
            if sender == self.polish_checkbox:
                self.translate_checkbox.setChecked(False)
                self.translate_checkbox.setEnabled(False)
            elif sender == self.translate_checkbox:
                self.polish_checkbox.setChecked(False)
                self.polish_checkbox.setEnabled(False)
        else:
            # 如果取消勾选，则启用另一个
            if not self.polish_checkbox.isChecked() and not self.translate_checkbox.isChecked():
                self.polish_checkbox.setEnabled(True)
                self.translate_checkbox.setEnabled(True)

    def accept(self):
        """当用户点击"检查"按钮时，组合模式字符串"""
        is_polish = self.polish_checkbox.isChecked()
        is_translate = self.translate_checkbox.isChecked()
        is_judge = (self.mode_combo.currentText() == self.tra("精准判断"))

        if not is_polish and not is_translate:
            # 理论上不会发生，因为逻辑上至少有一个被选中
            pass # 可以选择弹窗提示用户必须选择一个

        mode_parts = []
        if is_polish:
            mode_parts.append("polish")
        if is_judge:
            mode_parts.append("judge")
            
        self.check_mode = "_".join(mode_parts) if mode_parts else "report" # 默认是翻译的宏观统计
        
        super().accept()