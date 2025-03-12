from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CardWidget, ToolButton, FluentIcon as FIF, TransparentPushButton

from Base.Base import Base

class ConfigImportExportCard(CardWidget, Base):
    def __init__(self, init=None):
        super().__init__()
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(8)

        # 内容容器布局（保留原结构）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # 创建按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(0)
        
        # 创建按钮和间距
        self.left_button = TransparentPushButton(FIF.DOWNLOAD, self.tra('导入'), self)
        self.right_button = TransparentPushButton(FIF.SHARE, self.tra('导出'), self)
        self.spacer = QWidget()
        self.spacer.setFixedWidth(10)  # 初始间距

        # 填充按钮布局
        button_layout.addWidget(self.left_button)
        button_layout.addWidget(self.spacer)
        button_layout.addWidget(self.right_button)


        # 组合布局
        content_layout.addLayout(button_layout)
        content_layout.addStretch(1)

        self.main_layout.addLayout(content_layout)

        if init:
            init(self)
