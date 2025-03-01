from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout, QFrame, QSizePolicy,
                             QLabel, QInputDialog)

from qfluentwidgets import (CardWidget, CaptionLabel, MessageBoxBase, PlainTextEdit, StrongBodyLabel, SubtitleLabel, ToolButton, ComboBox,
                            FluentIcon, BodyLabel, isDarkTheme)

from Widget.Separator import Separator

class DialogueFragmentCard(CardWidget):
    contentChanged = pyqtSignal(str)  # 内容变化信号
    delete_requested = pyqtSignal()
    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self._setup_ui()

    def _setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # ------------------ 第一部分：头部 ------------------
        header_layout = QHBoxLayout()
        
        # 左侧角色选择
        role_layout = QHBoxLayout()
        self.role_combo = ComboBox(self)
        self.role_combo.addItems(["用户", "模型", "系统"])
        role_layout.addWidget(self.role_combo, alignment=Qt.AlignLeft)
        role_layout.setSpacing(8)
        
        # 右侧工具按钮
        self.edit_btn = ToolButton(FluentIcon.EDIT, self)
        self.delete_btn = ToolButton(FluentIcon.DELETE, self)
        
        # 组合布局
        header_layout.addLayout(role_layout)
        header_layout.addStretch()
        header_layout.addWidget(self.edit_btn)
        header_layout.addWidget(self.delete_btn)
        main_layout.addLayout(header_layout)

        # 添加分割线
        main_layout.addWidget(Separator())

        # ------------------ 第二部分：内容区域 ------------------
        self.content_label = BodyLabel("", self)
        main_layout.addWidget(self.content_label, stretch=1)


        # ------------------ 第三部分：系统提示（初始隐藏）------------------

        # 添加系统提示相关分割线（初始隐藏）
        self.system_separator = Separator()
        self.system_separator.hide()
        main_layout.addWidget(self.system_separator)

        self.system_label = CaptionLabel("", self)
        self.system_label.hide()
        main_layout.addWidget(self.system_label)


        # ------------------ 第四部分：AI回复（初始隐藏）------------------
        # 添加AI回复相关分割线（初始隐藏）
        self.response_separator = Separator()
        self.response_separator.hide()
        main_layout.addWidget(self.response_separator)

        self.response_label = CaptionLabel("", self)
        self.response_label.hide()
        main_layout.addWidget(self.response_label)


        # 连接信号
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        # 连接信号
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.role_combo.currentTextChanged.connect(self._emit_config_update)
        self.contentChanged.connect(self._emit_config_update)


    def load_config(self, settings):
        """从用户配置加载数据，初始化属性"""
        self.role_combo.setCurrentText(settings.get("role", "用户"))
        self.set_content(settings.get("content", ""))


    def _on_delete_clicked(self):
        """触发删除事件"""
        self.delete_requested.emit()

    def _emit_config_update(self):
        """发送配置更新"""
        self.config_changed.emit({
            "role": self.role_combo.currentText(),
            "content": self.content(),
            "system_info": self.system_label.text()
        })

    def set_content(self, text: str):
        """设置内容并触发更新"""
        super().set_content(text)
        self._emit_config_update()

    def _on_edit_clicked(self):
        """编辑按钮点击事件"""
        dialog = EditContentMessageBox(self.content(), self.window())
        if dialog.exec_():
            new_text = dialog.text_edit.toPlainText().strip()
            if new_text:
                self.set_content(new_text)
                self.contentChanged.emit(new_text)

    def set_content(self, text: str):
        """设置内容文本"""
        self.content_label.setText(text)
        self.content_label.adjustSize()
        self.adjustSize()

    def set_system_info(self, text: str):
        """设置系统提示信息"""
        if text.strip():  # 有内容时显示
            self.system_label.setText(text)
            self.system_separator.setVisible(True)
            self.system_label.setVisible(True)
        else:  # 无内容时隐藏
            self.system_label.clear()
            self.system_separator.setVisible(False)
            self.system_label.setVisible(False)
        self.adjustSize()

    def set_response_info(self, text: str):
        """设置AI回复信息"""
        if text.strip():  # 有内容时显示
            self.response_label.setText(text)
            self.response_separator.setVisible(True)
            self.response_label.setVisible(True)
        else:  # 无内容时隐藏
            self.response_label.clear()
            self.response_separator.setVisible(False)
            self.response_label.setVisible(False)
        self.adjustSize()


    def content(self) -> str:
        """获取内容文本"""
        return self.content_label.text()




class EditContentMessageBox(MessageBoxBase):
    """自定义内容编辑消息框"""
    
    def __init__(self, initial_text: str, parent=None):
        super().__init__(parent)

        # 创建垂直布局用于存放所有选项行
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(0)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.addLayout(self.rows_layout)

        # 创建文本编辑框
        self.text_edit = PlainTextEdit(self)
        self.text_edit.setPlainText(initial_text)
        
        self.viewLayout.addWidget(self.text_edit)
        
        # 调整对话框尺寸
        self.widget.setMinimumWidth(700)