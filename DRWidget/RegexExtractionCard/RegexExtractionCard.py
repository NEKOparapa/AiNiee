from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QFrame

from qfluentwidgets import (CardWidget, CaptionLabel, LineEdit, ToolButton,
                            FluentIcon, BodyLabel, StrongBodyLabel, ComboBox)

from Widget.Separator import Separator
from Base.Base import Base

class RegexExtractionCard(CardWidget,Base):
    delete_requested = pyqtSignal()  # 删除请求信号
    config_changed = pyqtSignal(dict)  # 配置变更信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.default_config = {
            "extractor_type": "RegexExtraction",
            "system_info": '',
            "input_source": "第一次回复内容",
            "extract_rule": "",
            "placeholder": "{extracted_rex_content}",
            "repetitive_processing": "last"
        }
        # UI控件初始化
        self.extract_rule_input = LineEdit(parent=self)
        self.placeholder_input = LineEdit(parent=self)
        self.combo_box = ComboBox(self)  # 新增下拉框
        self._setup_ui()
        self._connect_signals()
        self._init_combo_box()  # 初始化下拉框

    def _init_combo_box(self):
        """初始化重复处理下拉框"""
        self.combo_box.addItems(["last", "join"])
        self.combo_box.setCurrentText(self.default_config["repetitive_processing"])

    def _setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # ------------------ 第一部分：头部 ------------------
        header_layout = QHBoxLayout()
        title_label = StrongBodyLabel(self.tra("简易正则提取器"), self)
        self.delete_btn = ToolButton(FluentIcon.DELETE, self)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.delete_btn)
        main_layout.addLayout(header_layout)

        # ------------------ 第二部分：功能说明区域 ------------------
        main_layout.addWidget(Separator())

        # 创建水平布局容器
        description_layout = QHBoxLayout()
        description_layout.setContentsMargins(0, 8, 0, 8)
        description_layout.setSpacing(16)

        # 创建信息块
        input_source_block = self._create_info_block(self.tra("输入源"), BodyLabel(self.tra("第一次回复内容")))
        rule_block = self._create_input_block(self.tra("正则表达式"), self.extract_rule_input, prefix="", suffix="")
        placeholder_block = self._create_input_block(self.tra("文本占位符"), self.placeholder_input, prefix="", suffix="")
        repetitive_block = self._create_processing_block(self.tra("多项处理"), self.combo_box)  # 新增重复处理块

        # 将占位符和重复处理组合成水平布局
        combined_block = QFrame()
        combined_layout = QHBoxLayout(combined_block)
        combined_layout.setContentsMargins(0, 0, 0, 0)
        combined_layout.addWidget(placeholder_block)
        combined_layout.addWidget(repetitive_block)

        # 添加所有块到布局
        description_layout.addWidget(input_source_block, 1)
        description_layout.addWidget(rule_block, 1)
        description_layout.addWidget(combined_block, 2)  # 组合块占双倍空间

        main_layout.addLayout(description_layout)

        # ------------------ 第三部分：系统提示 ------------------
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
        self.combo_box.setCurrentText(settings.get("repetitive_processing", "last"))

    def _create_info_block(self,title, content_widget):
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



    def _create_processing_block(self, title, content_widget):
        """创建信息块"""
        block = QFrame(self)
        layout = QVBoxLayout(block)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        
        title_label = CaptionLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addWidget(content_widget)
        return block

    def _create_input_block(self, title, input_widget, prefix="", suffix=""):
        """创建带输入框的信息块"""
        block = QFrame(self)
        layout = QVBoxLayout(block)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        title_label = CaptionLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        
        input_layout = QHBoxLayout()
        input_layout.addStretch()
        if prefix:
            input_layout.addWidget(BodyLabel(prefix))
        input_layout.addWidget(input_widget)
        if suffix:
            input_layout.addWidget(BodyLabel(suffix))
        input_layout.addStretch()

        layout.addWidget(title_label)
        layout.addLayout(input_layout)
        return block

    def _connect_signals(self):
        """连接信号"""
        self.delete_btn.clicked.connect(self.delete_requested.emit)
        self.extract_rule_input.textChanged.connect(self._on_config_change)
        self.placeholder_input.textChanged.connect(self._on_config_change)
        self.combo_box.currentTextChanged.connect(self._on_config_change)  # 新增信号连接

    def _on_config_change(self):
        """配置变更处理"""
        self.config_changed.emit(self.get_config())

    def get_config(self) -> dict:
        """获取当前配置"""
        return {
            **self.default_config,
            "extract_rule": self.extract_rule_input.text(),
            "placeholder": self.placeholder_input.text(),
            "system_info": self.system_label.text(),
            "repetitive_processing": self.combo_box.currentText()  # 新增配置项
        }

    def set_system_info(self, text: str):
        """设置系统提示信息"""
        if text.strip():
            self.system_label.setText(text)
            self.system_separator.show()
            self.system_label.show()
        else:
            self.system_label.clear()
            self.system_separator.hide()
            self.system_label.hide()
        self.adjustSize()