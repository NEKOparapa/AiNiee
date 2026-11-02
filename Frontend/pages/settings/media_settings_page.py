"""Shared layout and automatic persistence for media task settings."""

import copy

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QWidget
from qfluentwidgets import SingleDirectionScrollArea

from Frontend.components.cards.settings_section import SettingsSection
from Frontend.components.toast import ToastMixin
from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin


class MediaSettingsPage(QFrame, ConfigMixin, ToastMixin, Base):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setObjectName(text.replace(" ", "-"))
        self._loading = True
        self._baseline = None
        self._config_snapshot = {}
        self._ready = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(lambda: self._save_settings(report_validation=False))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 20)

        self.scroll_area = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.scroll_area.viewport().setObjectName("mediaSettingsViewport")
        self.scroll_area.viewport().setStyleSheet("QWidget#mediaSettingsViewport { background: transparent; }")
        self.editor = QWidget()
        self.editor.setObjectName("mediaSettingsEditor")
        self.editor.setStyleSheet("QWidget#mediaSettingsEditor { background: transparent; }")
        self.editor_layout = QVBoxLayout(self.editor)
        self.editor_layout.setContentsMargins(0, 0, 8, 4)
        self.editor_layout.setSpacing(16)
        self.scroll_area.setWidget(self.editor)
        layout.addWidget(self.scroll_area, 1)

        self._build_fields()
        self.editor_layout.addStretch(1)
        self.editor.setEnabled(False)
        self._read_config()
        self._ready = True

    def _add_section(self, title, icon, description=""):
        section = SettingsSection(title, icon, description, self.editor)
        self.editor_layout.addWidget(section)
        return section

    def _apply_config(self, config):
        values = self._read_settings(config)
        self._save_timer.stop()
        self._loading = True
        try:
            self._load_fields(values)
            self._baseline = self._form_values()
            self._config_snapshot = copy.deepcopy(config)
            self.editor.setEnabled(True)
        finally:
            self._loading = False

    def _read_config(self):
        try:
            self._apply_config(self.load_config())
        except Exception:
            self.error_toast(self.tra("读取失败"), self.tra("无法读取任务设置，请检查后端连接后重新打开此页面。"))

    def showEvent(self, event):
        super().showEvent(event)
        if self._ready and not self._is_dirty():
            self._read_config()

    def _is_dirty(self):
        return self._baseline is not None and self._form_values() != self._baseline

    def _schedule_save(self, *_):
        if self._loading:
            return
        if self._is_dirty():
            self._save_timer.start()
        else:
            self._save_timer.stop()

    def prepare_to_leave(self):
        # Flush edits before navigation or shutdown; retain them if saving fails.
        return self._save_settings()

    def _save_settings(self, *, report_validation=True):
        self._save_timer.stop()
        if self._loading or not self._is_dirty():
            return True
        values = self._form_values()

        # A partially typed size is not ready for persistence. Validate locally
        # before making a request, and report errors when editing finishes.
        try:
            self._build_update(self._config_snapshot, values)
        except ValueError as error:
            if report_validation:
                self.error_toast(self.tra("配置无效"), self.tra(str(error)))
            return False

        def update(current):
            current.update(self._build_update(current, values))

        try:
            config = self.update_config(update)
            self._config_snapshot = copy.deepcopy(config)
            # Keep the active editor and caret untouched after an automatic save.
            self._baseline = copy.deepcopy(values)
            return True
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
        except Exception:
            self.error_toast(self.tra("自动保存失败"), self.tra("修改尚未保存，请检查后端连接后重试。"))
        return False
