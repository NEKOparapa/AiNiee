# UserInterface/EditView/components/text_view_page.py

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QFrame)
from qfluentwidgets import CardWidget, TitleLabel, BodyLabel

class TextViewPage(QWidget):
    def __init__(self, text_data: list, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("TextViewPage")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.scroll_content_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content_widget)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(10)

        self._populate_data(text_data)

        self.scroll_area.setWidget(self.scroll_content_widget)
        self.main_layout.addWidget(self.scroll_area)

    def _populate_data(self, text_data: list):
        if not text_data:
            self.scroll_layout.addWidget(BodyLabel("没有可供预览的文本。", self))
            return

        for i, row_data in enumerate(text_data):
            card = CardWidget(self)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(8)
            card_layout.setContentsMargins(15, 10, 15, 10)

            source_title = TitleLabel(f"原文 (第 {row_data['row']} 行)", self)
            card_layout.addWidget(source_title)

            source_content = BodyLabel(row_data['source'], self)
            source_content.setWordWrap(True)
            card_layout.addWidget(source_content)

            card_layout.addSpacing(10)

            if row_data['translation']:
                trans_title = BodyLabel("译文:", self)
                card_layout.addWidget(trans_title)
                trans_content = BodyLabel(row_data['translation'], self)
                trans_content.setWordWrap(True)
                card_layout.addWidget(trans_content)
                card_layout.addSpacing(5)

            if row_data['polish']:
                polish_title = BodyLabel("润文:", self)
                card_layout.addWidget(polish_title)
                polish_content = BodyLabel(row_data['polish'], self)
                polish_content.setWordWrap(True)
                card_layout.addWidget(polish_content)

            self.scroll_layout.addWidget(card)

        self.scroll_layout.addStretch(1)