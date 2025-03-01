from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import CardWidget, CaptionLabel, SubtitleLabel, ToolButton, FluentIcon as FIF

class EndPhaseCard(CardWidget):
    def __init__(self, title: str, description: str, init=None):  # 添加 placeholder_width 参数
        super().__init__()

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

        # 添加伸缩因子确保居中
        content_layout.addStretch(1)
        content_layout.addLayout(text_container)
        content_layout.addStretch(1)

        # 占位标签
        self.placeholder_widget = QWidget(self)
        self.placeholder_widget.setFixedWidth(40)  # 设置固定宽度
        self.placeholder_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) # 确保不伸缩
        content_layout.addWidget(self.placeholder_widget)


        self.main_layout.addLayout(content_layout)

        if init:
            init(self)