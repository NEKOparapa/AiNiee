from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QSizePolicy
from qfluentwidgets import CardWidget, CaptionLabel, SubtitleLabel, ToolButton, FluentIcon as FIF

class TestBreakpointCard(CardWidget):
    def __init__(self, title: str, description: str, breakpoint_position: str, init=None):
        super().__init__()
        self.breakpoint_position = breakpoint_position

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(8)

        # 内容布局
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # 文本容器
        text_container = QVBoxLayout()
        text_container.setAlignment(Qt.AlignCenter)
        
        # 标题和描述
        self.title_label = SubtitleLabel(title, self)
        self.title_label.setAlignment(Qt.AlignCenter)
        
        self.description_label = CaptionLabel(description, self)
        self.description_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        self.description_label.setAlignment(Qt.AlignCenter)

        text_container.addWidget(self.title_label)
        text_container.addWidget(self.description_label)
        
        # 添加伸缩因子确保文本容器居中
        content_layout.addStretch(1)
        content_layout.addLayout(text_container)
        content_layout.addStretch(1)

        # 按钮部分（保持右侧对齐但不影响居中）
        self.tool_button = ToolButton(FIF.SYNC, self)
        self.tool_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)  # 固定按钮大小
        content_layout.addWidget(self.tool_button)

        self.main_layout.addLayout(content_layout)

        if init:
            init(self)