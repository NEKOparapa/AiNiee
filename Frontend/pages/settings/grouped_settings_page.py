"""Consistent grouped task settings and in-page management editors."""

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QStackedWidget, QVBoxLayout
from qfluentwidgets import (
    CaptionLabel, FluentIcon, PillPushButton, SpinBox, SwitchButton,
    TitleLabel, TransparentPushButton,
)

from Frontend.components.cards.settings_section import SettingsSection
from Frontend.components.toast import ToastMixin
from Frontend.core.config import ConfigMixin
from Frontend.pages.settings.media_settings_page import MediaSettingsPage


class CompactSettingsSection(SettingsSection):
    def __init__(self, title, icon, description, parent, *, expanded=True):
        super().__init__(title, icon, description, parent, collapsible=True)
        self.layout().setContentsMargins(20, 14, 20, 16)
        self.layout().setSpacing(14)
        self.fields.setSpacing(10)
        self.expand_button.setChecked(expanded)

    def add_field(self, label, widget, description="", *, multiline=False):
        super().add_field(label, widget, description, multiline=multiline)
        if not multiline and not isinstance(widget, (SpinBox, SwitchButton)):
            widget.setFixedWidth(240)
        return self.fields.itemAt(self.fields.count() - 1).widget()


class GroupedSettingsPage(MediaSettingsPage):
    editorRequested = pyqtSignal(str)

    def __init__(self, text, parent=None):
        self.sections = {}
        self.jump_buttons = {}
        self.jump_layout = None
        self.save_status = None
        super().__init__(text, parent)
        if self.jump_layout is not None:
            self.jump_layout.addStretch()

    def _build_header(self, title, description):
        self.layout().setContentsMargins(28, 24, 24, 20)
        self.layout().setSpacing(18)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(7)
        heading.addWidget(TitleLabel(self.tra(title), self))
        caption = CaptionLabel(self.tra(description), self)
        caption.setWordWrap(True)
        heading.addWidget(caption)
        header.addLayout(heading, 1)
        self.save_status = CaptionLabel(self.tra("自动保存"), self)
        self.save_status.setTextColor(QColor("#68717d"), QColor("#a5abb4"))
        header.addWidget(self.save_status, 0, Qt.AlignTop)
        self.layout().insertLayout(0, header)
        self.jump_layout = QHBoxLayout()
        self.jump_layout.setSpacing(8)
        self.layout().insertLayout(1, self.jump_layout)
        self.editor_layout.setSpacing(14)

    def _add_section(self, title, icon, description="", *, expanded=True):
        section = CompactSettingsSection(title, icon, description, self.editor, expanded=expanded)
        self.editor_layout.addWidget(section)
        self.sections[title] = section
        if self.jump_layout is None:
            return section
        button = PillPushButton(self.tra(title), self)
        button.setFixedHeight(30)
        button.setChecked(len(self.sections) == 1)
        button.clicked.connect(lambda: self._jump(title))
        self.jump_layout.addWidget(button)
        self.jump_buttons[title] = button
        return section

    def _jump(self, title):
        section = self.sections[title]
        section.expand_button.setChecked(True)
        for name, button in self.jump_buttons.items():
            button.setChecked(name == title)
        QTimer.singleShot(0, lambda: self.scroll_area.ensureWidgetVisible(section, 0, 12))

    def _schedule_save(self, *_):
        super()._schedule_save()
        if not self._loading and self.save_status is not None:
            self.save_status.setText(self.tra("待保存") if self._is_dirty() else self.tra("自动保存"))

    def _save_settings(self, *, report_validation=True):
        saved = super()._save_settings(report_validation=report_validation)
        if self.save_status is not None:
            self.save_status.setText(self.tra("自动保存") if saved else self.tra("保存失败"))
        return saved


class SettingsWorkspacePage(QFrame, ConfigMixin, ToastMixin):
    """The overview and its editors share one global navigation entry."""

    def __init__(self, text, parent, *, title, overview_factory):
        super().__init__(parent)
        self.setObjectName(text)
        self.page_title = title
        self.details = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack)
        self.overview = overview_factory(self)
        self.stack.addWidget(self.overview)
        self.overview.editorRequested.connect(self.open_editor)

    def open_editor(self, key):
        if not self.prepare_to_leave():
            return
        if key not in self.details:
            try:
                editor = self._create_editor(key)
            except Exception:
                self.error_toast(self.tra("读取失败"), self.tra("无法读取任务设置，请检查后端连接后重新打开此页面。"))
                return
            detail = QFrame(self)
            layout = QVBoxLayout(detail)
            layout.setContentsMargins(28, 16, 24, 0)
            header = QHBoxLayout()
            back = TransparentPushButton(FluentIcon.RETURN, self.tra("返回{page}").format(page=self.tra(self.page_title)), detail)
            back.clicked.connect(self.back_to_settings)
            header.addWidget(back)
            header.addStretch()
            header.addWidget(CaptionLabel(self.tra(self.page_title) + " / " + self.tra(self._editor_title(key)), detail))
            layout.addLayout(header)
            layout.addWidget(editor, 1)
            editor.layout().setContentsMargins(0, 12, 0, 24)
            detail.editor = editor
            self.details[key] = detail
            self.stack.addWidget(detail)
        self.stack.setCurrentWidget(self.details[key])

    def _editor_title(self, key):
        return "管理提示词"

    def _create_editor(self, key):
        raise NotImplementedError

    def back_to_settings(self):
        if self.prepare_to_leave():
            self.overview._read_config()
            self.stack.setCurrentWidget(self.overview)

    def prepare_to_leave(self):
        current = self.stack.currentWidget()
        editor = current if current is self.overview else current.editor
        leave = getattr(editor, "prepare_to_leave", None)
        return leave() if callable(leave) else True
