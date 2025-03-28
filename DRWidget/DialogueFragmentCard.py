from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout)

from qfluentwidgets import (CardWidget, CaptionLabel, MessageBoxBase, PlainTextEdit,ToolButton, ComboBox,
                            FluentIcon, BodyLabel)

from Widget.Separator import Separator
from Base.Base import Base

class DialogueFragmentCard(CardWidget,Base):
    contentChanged = pyqtSignal(str)  # 内容变化信号
    delete_requested = pyqtSignal()
    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        # 初始化角色选项数据
        self._setup_role_data()
        # 布局
        self._setup_ui()

    def _setup_role_data(self):
        """初始化角色多语言数据"""
        self.role_pairs = [
            (self.tra("用户"), "user"),
            (self.tra("模型"), "assistant"),
            (self.tra("系统"), "system")
        ]
        self.translated_role_pairs = [
            (self.tra(display), value) for display, value in self.role_pairs
        ]
        self.role_options = [display for display, _ in self.translated_role_pairs]

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
        self.role_combo.addItems(self.role_options)  # 使用翻译后的选项
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


        # 编辑按钮连接信号
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        self.contentChanged.connect(self._emit_config_update)

        # 删除按钮连接信号
        self.delete_btn.clicked.connect(self._on_delete_clicked)

        # 用户组下拉框连接信号
        self.role_combo.currentTextChanged.connect(self._emit_config_update)



    def load_config(self, settings):
        """从用户配置加载数据，初始化属性"""
        # 根据存储的值设置当前选项
        current_value = settings.get("role", "user")
        index = next(
            (i for i, (_, value) in enumerate(self.translated_role_pairs) if value == current_value),
            0  # 默认第一个选项
        )
        self.role_combo.setCurrentIndex(max(0, index))
        
        # 原有内容初始化保持不变
        self.set_content(settings.get("content", ""))


    def _on_delete_clicked(self):
        """触发删除事件"""
        self.delete_requested.emit()

    def _emit_config_update(self):
        """发送配置更新（新增角色值转换）"""
        current_display = self.role_combo.currentText()
        # 查找对应的存储值
        current_value = next(
            (value for display, value in self.translated_role_pairs if display == current_display),
            "user"  # 默认值
        )
        
        self.config_changed.emit({
            "role": current_value,  # 存储原始值
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


    def content(self) -> str:
        """获取编辑框的文本"""
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
        self.widget.setMinimumWidth(900)
        self.widget.setMinimumHeight(600)