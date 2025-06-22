from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QFrame)
from PyQt5.QtCore import Qt 
from qfluentwidgets import CardWidget, BodyLabel, SingleDirectionScrollArea

class TextViewPage(QWidget):
    def __init__(self, text_data: list, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("TextViewPage")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_area = SingleDirectionScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background-color: transparent;")

        self.scroll_content_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content_widget)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(10) 

        self._populate_data(text_data)

        self.scroll_area.setWidget(self.scroll_content_widget)
        self.main_layout.addWidget(self.scroll_area)

    def _populate_data(self, text_data: list):
        if not text_data:
            self.scroll_layout.addWidget(BodyLabel("No Text", self))
            return

        for i, row_data in enumerate(text_data):
            card = CardWidget(self)
            card_layout = QVBoxLayout(card)
            
            card_layout.setSpacing(2)  # 将间距从 8 减小到 2
            card_layout.setContentsMargins(15, 10, 15, 10)

            # 原文
            source_content = BodyLabel(row_data['source'], self)
            source_content.setWordWrap(True)
            source_content.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            card_layout.addWidget(source_content)

            # 译文
            if row_data['translation']:
                trans_content = BodyLabel(row_data['translation'], self)
                trans_content.setWordWrap(True)
                trans_content.setAlignment(Qt.AlignLeft | Qt.AlignVCenter) # 确保左对齐
                card_layout.addWidget(trans_content)

            # 润文
            if row_data['polish']:
                polish_content = BodyLabel(row_data['polish'], self)
                polish_content.setWordWrap(True)
                polish_content.setAlignment(Qt.AlignLeft | Qt.AlignVCenter) # 确保左对齐
                card_layout.addWidget(polish_content)

            self.scroll_layout.addWidget(card)

        # 将所有卡片推到顶部，防止垂直居中
        self.scroll_layout.addStretch(1)