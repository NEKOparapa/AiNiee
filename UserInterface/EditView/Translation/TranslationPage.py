from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import SingleDirectionScrollArea

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.EditView.Translation.BottomCommandBar import BottomCommandBar
from UserInterface.EditView.Translation.LanguageSettingsCard import LanguageSettingsCard
from UserInterface.EditView.Translation.MonitoringPage import MonitoringPage


class TranslationPage(ConfigMixin, Base, QWidget):
    FLOATING_BAR_GAP = 12
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
        self.language_settings_card = LanguageSettingsCard(self)
        self.bottom_bar.raise_()
        self.language_settings_card.raise_()
        self._position_floating_cards()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_floating_cards()

    def _position_floating_cards(self) -> None:
        bottom_bar_width = self.bottom_bar.sizeHint().width()
        language_card_width = self.language_settings_card.sizeHint().width()
        total_width = bottom_bar_width + self.FLOATING_BAR_GAP + language_card_width

        x = max(self.FLOATING_BAR_SIDE_MARGIN, (self.width() - total_width) // 2)
        y = self.height() - max(self.bottom_bar.height(), self.language_settings_card.height()) - self.FLOATING_BAR_BOTTOM_MARGIN

        self.bottom_bar.setGeometry(x, max(0, y), bottom_bar_width, self.bottom_bar.height())
        self.language_settings_card.setGeometry(
            x + bottom_bar_width + self.FLOATING_BAR_GAP,
            max(0, y),
            language_card_width,
            self.language_settings_card.height(),
        )

    def enable_continue_button(self, enable: bool) -> None:
        self.bottom_bar.enable_continue_button(enable)
