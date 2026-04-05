from PyQt5.QtWidgets import QStackedWidget, QVBoxLayout
from qfluentwidgets import CardWidget, TabBar


class PageCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.tab_bar = TabBar(self)
        self.tab_bar.setTabMaximumWidth(160)
        self.tab_bar.setTabShadowEnabled(False)
        self.tab_bar.setScrollable(True)
        self.layout.addWidget(self.tab_bar)

        self.stacked_widget = QStackedWidget(self)
        self.layout.addWidget(self.stacked_widget)
