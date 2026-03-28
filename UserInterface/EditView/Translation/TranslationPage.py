from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import SingleDirectionScrollArea

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.EditView.Translation.BottomCommandBar import BottomCommandBar
from UserInterface.EditView.Translation.MonitoringPage import MonitoringPage


class TranslationPage(ConfigMixin, Base, QWidget):
    FLOATING_BAR_MAX_WIDTH = 720
    FLOATING_BAR_SIDE_MARGIN = 24
    FLOATING_BAR_BOTTOM_MARGIN = 20
    FLOATING_BAR_CONTENT_PADDING = 112

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TranslationPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(0)

        self.monitoring_page = MonitoringPage(self)
        self.monitoring_page.setStyleSheet("QWidget { background: transparent; }")
        self.scroller = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.scroller.setWidget(self.monitoring_page)
        layout.addWidget(self.scroller, 1)

        left, top, right, _ = self.monitoring_page.container.getContentsMargins()
        self.monitoring_page.container.setContentsMargins(
            left,
            top,
            right,
            self.FLOATING_BAR_CONTENT_PADDING,
        )

        self.bottom_bar = BottomCommandBar(self)
        self.bottom_bar.raise_()
        self._position_bottom_bar()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_bottom_bar()

    def _position_bottom_bar(self) -> None:
        available_width = max(0, self.width() - self.FLOATING_BAR_SIDE_MARGIN * 2)
        preferred_width = min(self.bottom_bar.sizeHint().width(), self.FLOATING_BAR_MAX_WIDTH)
        bar_width = min(preferred_width, available_width)
        x = max(self.FLOATING_BAR_SIDE_MARGIN, (self.width() - bar_width) // 2)
        y = self.height() - self.bottom_bar.height() - self.FLOATING_BAR_BOTTOM_MARGIN
        self.bottom_bar.setGeometry(x, max(0, y), bar_width, self.bottom_bar.height())

    def enable_continue_button(self, enable: bool) -> None:
        self.bottom_bar.enable_continue_button(enable)
