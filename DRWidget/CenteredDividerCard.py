from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout
from PyQt5.QtCore import Qt
from qfluentwidgets import CardWidget, CaptionLabel, StrongBodyLabel, HyperlinkButton,SubtitleLabel

class CenteredDividerCard(CardWidget):

    def __init__(self, title: str, description: str, url: str, link_text: str, init=None):
        super().__init__(None)

        # 设置容器
        self.setBorderRadius(4)
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(16, 16, 16, 16)  # 左、上、右、下

        # 文本容器（新增中间容器）
        center_container = QVBoxLayout()
        center_container.setAlignment(Qt.AlignCenter)
        
        # 文本控件
        self.vbox = QVBoxLayout()
        self.vbox.setAlignment(Qt.AlignCenter)  # 垂直居中

        self.title_label = SubtitleLabel(title, self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.description_label = CaptionLabel(description, self)
        self.description_label.setTextColor(QColor(96, 96, 96), QColor(160, 160, 160))
        self.description_label.setAlignment(Qt.AlignCenter)

        self.vbox.addWidget(self.title_label)
        self.vbox.addWidget(self.description_label)
        
        # 将文本布局添加到中间容器
        center_container.addLayout(self.vbox)
        
        # 添加伸缩因子确保居中
        self.hbox.addStretch(1)
        self.hbox.addLayout(center_container)
        self.hbox.addStretch(1)

        # 超链接按钮
        self.hyperlinkButton1 = HyperlinkButton(
            url=url,
            text=link_text,
            parent=self
        )
        self.hbox.addWidget(self.hyperlinkButton1)

        if init:
            init(self)

