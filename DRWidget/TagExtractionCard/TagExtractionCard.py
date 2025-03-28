from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout, QFrame,)

from qfluentwidgets import (CardWidget, CaptionLabel, LineEdit, ToolButton,
                            FluentIcon, BodyLabel, StrongBodyLabel)

from Widget.Separator import Separator
from Base.Base import Base

class TagExtractionCard(CardWidget,Base):
    delete_requested = pyqtSignal()  # 删除请求信号
    config_changed = pyqtSignal(dict)  # 配置变更信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.default_config = {
            "extractor_type": "TagExtraction",
            "system_info": '',
            "input_source": "第一次回复内容",
            "extract_rule": "",
            "placeholder": "{extracted_tag_content}",
            "repetitive_processing": "last"
        }
        self.extract_rule_input = LineEdit(parent=self) # 提取规则输入框，默认值，使用关键字参数
        self.placeholder_input = LineEdit(parent=self) # 文本占位符输入框，默认值，使用关键字参数
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # ------------------ 第一部分：头部 ------------------
        header_layout = QHBoxLayout()
        title_label = StrongBodyLabel(self.tra("标签提取器"), self)
        self.delete_btn = ToolButton(FluentIcon.DELETE, self)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.delete_btn)
        main_layout.addLayout(header_layout)

        # ------------------ 第二部分：功能说明区域 ------------------
        main_layout.addWidget(Separator())

        def create_info_block(title, content_widget):
            """创建信息展示块，content_widget 可以是 QLabel 或其他控件"""
            block = QFrame(self)
            layout = QVBoxLayout(block)
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(4)

            # 标题部分
            title_label = CaptionLabel(title)
            title_label.setAlignment(Qt.AlignCenter)


            # 添加元素
            layout.addWidget(title_label, 0, Qt.AlignCenter)
            layout.addWidget(content_widget, 0, Qt.AlignCenter) # 添加传入的 widget
            return block

        def create_input_block(title, input_widget, prefix="", suffix=""):
            """创建带输入框的信息块"""
            block = QFrame(self)
            layout = QVBoxLayout(block)
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(4)

            # 标题部分
            title_label = CaptionLabel(title)
            title_label.setAlignment(Qt.AlignCenter)

            # 输入行 + 标签 水平布局
            input_layout = QHBoxLayout()
            input_layout.addStretch(0) # 左侧弹簧
            if prefix:
                prefix_label = BodyLabel(prefix)
                input_layout.addWidget(prefix_label)
            input_layout.addWidget(input_widget)
            if suffix:
                suffix_label = BodyLabel(suffix)
                input_layout.addWidget(suffix_label)
            input_layout.addStretch(0) # 右侧弹簧


            # 添加元素
            layout.addWidget(title_label, 0, Qt.AlignCenter)
            layout.addLayout(input_layout)
            return block


        # 创建水平布局容器
        description_layout = QHBoxLayout()
        description_layout.setContentsMargins(0, 8, 0, 8)
        description_layout.setSpacing(16)

        # 创建信息块
        input_source_block = create_info_block(self.tra("输入源"), BodyLabel(self.tra("第一次回复内容"))) # 输入源保持 BodyLabel
        rule_block = create_input_block(self.tra("提取规则"), self.extract_rule_input, prefix=self.tra("最后的"), suffix=self.tra("标签内文本")) # 提取规则改成输入框
        placeholder_block = create_input_block(self.tra("文本占位符"), self.placeholder_input, prefix="", suffix="") # 文本占位符改成输入框


        # 添加块到布局并设置拉伸比例
        description_layout.addWidget(input_source_block, 1)
        description_layout.addWidget(rule_block, 1)
        description_layout.addWidget(placeholder_block, 1)

        main_layout.addLayout(description_layout)

        # ------------------ 第三部分：系统提示------------------
        self.system_separator = Separator()
        self.system_separator.hide()
        main_layout.addWidget(self.system_separator)

        self.system_label = CaptionLabel("", self)
        self.system_label.hide()
        main_layout.addWidget(self.system_label)

    def load_config(self, settings):
        """从用户配置加载数据，初始化属性"""
        self.extract_rule_input.setText(settings.get("extract_rule", ""))
        self.placeholder_input.setText(settings.get("placeholder", ""))

    def _connect_signals(self):
        """连接信号"""
        self.delete_btn.clicked.connect(self.delete_requested.emit)
        self.extract_rule_input.textChanged.connect(self._on_config_change) # 监听输入框变化
        self.placeholder_input.textChanged.connect(self._on_config_change) # 监听输入框变化

    def _on_config_change(self):
        """配置变更时发射信号"""
        self.config_changed.emit(self.get_config())


    def get_config(self) -> dict:
        """获取当前配置"""
        return {
            **self.default_config,
            "extract_rule": self.extract_rule_input.text(), # 获取输入框的值
            "placeholder": self.placeholder_input.text(),   # 获取输入框的值
            "system_info": self.system_label.text()
        }

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
