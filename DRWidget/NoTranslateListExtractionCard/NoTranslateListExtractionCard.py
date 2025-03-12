from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QHBoxLayout, QVBoxLayout, QFrame,)

from qfluentwidgets import (CardWidget, CaptionLabel, ToolButton,
                            FluentIcon, BodyLabel, StrongBodyLabel)

from Widget.Separator import Separator
from Base.Base import Base

class NoTranslateListExtractionCard(CardWidget,Base):
    delete_requested = pyqtSignal()  # 删除请求信号
    config_changed = pyqtSignal(dict)  # 配置变更信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.default_config = {
            "extractor_type": "NoTranslateListExtraction",
            "system_info": '',
            "input_source": "第一次回复内容",
            "extract_rule": "提取code标签内容，并记录到禁翻表",
            "placeholder": "{extracted_code_content}",
            "repetitive_processing": "last"
        }
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # ------------------ 第一部分：头部 ------------------
        header_layout = QHBoxLayout()
        title_label = StrongBodyLabel(self.tra("禁翻表提取器"), self)
        self.delete_btn = ToolButton(FluentIcon.DELETE, self)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.delete_btn)
        main_layout.addLayout(header_layout)

        # ------------------ 第二部分：功能说明区域 ------------------
        main_layout.addWidget(Separator())  

        def create_info_block(title, content):
            """创建信息展示块"""
            block = QFrame(self)
            layout = QVBoxLayout(block)
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(4)

            # 标题部分
            title_label = CaptionLabel(title)
            title_label.setAlignment(Qt.AlignCenter)
            
            # 内容部分
            content_label = BodyLabel(content)
            content_label.setAlignment(Qt.AlignCenter)
            
            # 添加元素
            layout.addWidget(title_label, 0, Qt.AlignCenter)
            layout.addWidget(content_label, 0, Qt.AlignCenter)
            return block

        # 创建水平布局容器
        description_layout = QHBoxLayout()
        description_layout.setContentsMargins(0, 8, 0, 8)
        description_layout.setSpacing(16)

        # 创建三个信息块
        input_block = create_info_block(self.tra("输入源"), self.tra("第一次回复内容"))
        rule_block = create_info_block(self.tra("提取规则"), self.tra("提取code标签内容，并记录到禁翻表"))
        placeholder_block = create_info_block(self.tra("文本占位符"), "{extracted_code_content}")

        # 添加块到布局并设置拉伸比例
        description_layout.addWidget(input_block, 1)
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
        pass

    def _connect_signals(self):
        """连接信号"""
        self.delete_btn.clicked.connect(self.delete_requested.emit)


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

