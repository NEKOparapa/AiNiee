from PyQt5.QtWidgets import QFrame, QSizePolicy, QStackedWidget, QVBoxLayout
from qfluentwidgets import SegmentedWidget

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.PromptSettings.TranslationSettings.TranslationSettingsPage import TranslationSettingsPage
from UserInterface.Settings.ExtractionSettingsPage import ExtractionSettingsPage
from UserInterface.Settings.PolishingSettingsPage import PolishingSettingsPage


class AdvancedSettingsPage(QFrame, ConfigMixin, Base):
    DEFAULT_ROUTE = "translation"

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.container = QVBoxLayout(self)
        self.container.setSpacing(0)
        self.container.setContentsMargins(24, 10, 24, 24)

        self.tab_bar = SegmentedWidget(self)
        self.tab_bar.setFixedHeight(38)
        self.tab_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.stacked_widget = QStackedWidget(self)

        self.extraction_settings_page = ExtractionSettingsPage("extraction_settings_page", self)
        self.translation_settings_page = TranslationSettingsPage("translation_settings_page", self)
        self.polishing_settings_page = PolishingSettingsPage("polishing_settings_page", self)

        self.route_to_widget = {
            "extraction": self.extraction_settings_page,
            "translation": self.translation_settings_page,
            "polishing": self.polishing_settings_page,
        }

        for route_key, tab_text in (
            ("extraction", self.tra("提取设置")),
            ("translation", self.tra("翻译设置")),
            ("polishing", self.tra("润色设置")),
        ):
            item = self.tab_bar.addItem(
                routeKey=route_key,
                text=tab_text,
                onClick=lambda checked=False, key=route_key: self.switch_tab(key),
            )
            item.setFixedHeight(38)
            item.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        for widget in self.route_to_widget.values():
            self.stacked_widget.addWidget(widget)

        self.container.addWidget(self.tab_bar)
        self.container.addWidget(self.stacked_widget)

        self.switch_tab(self.DEFAULT_ROUTE)

    def switch_tab(self, route_key: str) -> None:
        widget = self.route_to_widget.get(route_key)
        if widget is None:
            return

        self.tab_bar.setCurrentItem(route_key)
        self.stacked_widget.setCurrentWidget(widget)
