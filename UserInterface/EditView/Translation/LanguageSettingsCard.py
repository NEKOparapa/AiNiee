from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import CardWidget, ComboBox, FluentIcon as FIF, IconWidget

from ModuleFolders.Config.Config import ConfigMixin


class LanguageSettingsCard(ConfigMixin, CardWidget):
    SOURCE_LANGUAGE_PAIRS = [
        ("自动检测", "auto"),
        ("日语", "japanese"),
        ("英语", "english"),
        ("韩语", "korean"),
        ("俄语", "russian"),
        ("德语", "german"),
        ("法语", "french"),
        ("简中", "chinese_simplified"),
        ("繁中", "chinese_traditional"),
        ("西班牙语", "spanish"),
        ("印尼语", "indonesian"),
        ("越南语", "vietnamese"),
        ("泰语", "thai"),
    ]
    TARGET_LANGUAGE_PAIRS = [
        ("简中", "chinese_simplified"),
        ("繁中", "chinese_traditional"),
        ("英语", "english"),
        ("日语", "japanese"),
        ("韩语", "korean"),
        ("俄语", "russian"),
        ("德语", "german"),
        ("法语", "french"),
        ("西班牙语", "spanish"),
        ("印尼语", "indonesian"),
        ("越南语", "vietnamese"),
        ("泰语", "thai"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setBorderRadius(18)

        self.source_language_pairs = [(self.tra(display), value) for display, value in self.SOURCE_LANGUAGE_PAIRS]
        self.target_language_pairs = [(self.tra(display), value) for display, value in self.TARGET_LANGUAGE_PAIRS]

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(18, 12, 18, 12)
        self.layout.setSpacing(8)

        self.source_language_combo = self._create_language_selector(
            pairs=self.source_language_pairs,
            config_key="source_language",
            default_value="auto",
        )
        self.language_direction_icon = self._create_language_arrow()
        self.target_language_combo = self._create_language_selector(
            pairs=self.target_language_pairs,
            config_key="target_language",
            default_value="chinese_simplified",
        )

        self.layout.addWidget(self.source_language_combo)
        self.layout.addWidget(self.language_direction_icon, 0, Qt.AlignCenter)
        self.layout.addWidget(self.target_language_combo)

    def _create_language_selector(
        self,
        pairs: list[tuple[str, str]],
        config_key: str,
        default_value: str,
    ) -> ComboBox:
        combo = ComboBox(self)
        combo.setFixedHeight(32)
        combo.addItems([display for display, _ in pairs])
        combo.setFixedWidth(self._get_language_selector_width(combo, pairs))
        combo.setCurrentIndex(self._get_language_index(pairs, config_key, default_value))
        combo.currentTextChanged.connect(
            lambda text, target_key=config_key, target_pairs=pairs, fallback=default_value: self._save_language_value(
                target_key,
                target_pairs,
                text,
                fallback,
            )
        )
        return combo

    def _create_language_arrow(self) -> IconWidget:
        arrow = IconWidget(FIF.RIGHT_ARROW, self)
        arrow.setFixedSize(16, 16)
        return arrow

    def _get_language_selector_width(self, combo: ComboBox, pairs: list[tuple[str, str]]) -> int:
        metrics = QFontMetrics(combo.font())
        max_text_width = max((metrics.horizontalAdvance(display) for display, _ in pairs), default=0)
        return max(20, max_text_width + 52)

    def _get_language_index(self, pairs: list[tuple[str, str]], config_key: str, default_value: str) -> int:
        current_value = self.load_config().get(config_key, default_value)
        return next((index for index, (_, value) in enumerate(pairs) if value == current_value), 0)

    def _save_language_value(
        self,
        config_key: str,
        pairs: list[tuple[str, str]],
        text: str,
        default_value: str,
    ) -> None:
        value = next((value for display, value in pairs if display == text), default_value)
        config = self.load_config()
        config[config_key] = value
        self.save_config(config)
