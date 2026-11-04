"""Bundled Microsoft Fluent icons with QFluentWidgets theme handling."""
from enum import Enum
from functools import lru_cache

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QIcon
from qfluentwidgets import FluentIconBase, Theme, getIconColor

from Frontend.core.resources import frontend_resource_path


# Resolve bundled resources before widgets start painting. Resource discovery
# checks environment variables and the filesystem; it must not run per frame.
_ICON_ROOT = frontend_resource_path("icons", "fluent")


@lru_cache(maxsize=14)
def _native_icon(path: str) -> QIcon:
    # Keep Qt's native SVG icon engine alive so it can reuse its rendered sizes.
    return QIcon(path)


class _BundledFluentIcon(FluentIconBase):
    def __init__(self, name):
        self._paths = {
            color: str(_ICON_ROOT / f"{name}_24_regular_{color}.svg")
            for color in ("black", "white")
        }

    def path(self, theme=Theme.AUTO):
        return self._paths[getIconColor(theme)]

    def icon(self, theme=Theme.AUTO, color=None):
        if color is not None:
            return super().icon(theme, color)
        return QIcon(_native_icon(self.path(theme)))

    def render(self, painter, rect, theme=Theme.AUTO, indexes=None, **attributes):
        if attributes:
            return super().render(painter, rect, theme, indexes, **attributes)
        # Navigation animations repaint frequently. Use Qt's native icon engine
        # instead of constructing a temporary QSvgRenderer in every paintEvent.
        _native_icon(self.path(theme)).paint(painter, QRectF(rect).toRect())


class ProviderIcon(_BundledFluentIcon, Enum):
    TRANSLATION = "chat_sparkle"
    TRANSCRIPTION = "sound_wave_circle"
    IMAGE_GENERATION = "image_sparkle"


class TaskSettingsIcon(_BundledFluentIcon, Enum):
    TEXT = "text_grammar_settings"
    IMAGE = "image_edit"
    AUDIO = "mic_settings"
    VIDEO = "video_settings"
