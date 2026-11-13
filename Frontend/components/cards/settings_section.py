"""Grouped settings fields shared by provider and task configuration pages."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel, CaptionLabel, CardWidget, FluentIcon, HorizontalSeparator,
    IconWidget, SpinBox, StrongBodyLabel, SwitchButton, TransparentPushButton,
)

from Frontend.core.config import ConfigMixin


class SettingsSection(CardWidget, ConfigMixin):
    def __init__(self, title, icon, description="", parent=None, *, collapsible=False):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if collapsible:
            self.expand_button = TransparentPushButton(self)
            self.expand_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.expand_button.setCursor(Qt.PointingHandCursor)
            self.expand_button.setCheckable(True)
            self.expand_button.setAccessibleName(self.tra(title))
            self.expand_button.setToolTip(self.tra("展开参数"))
            layout.addWidget(self.expand_button, 0, 0)

        # The labels size the row; clicks pass through to the button underneath.
        header_content = QWidget(self)
        header_content.setAttribute(Qt.WA_TransparentForMouseEvents, collapsible)
        layout.addWidget(header_content, 0, 0)
        header = self.header_layout = QHBoxLayout(header_content)
        header.setContentsMargins(20, 16, 20, 16)
        header.setSpacing(12)
        icon_widget = IconWidget(icon, header_content)
        icon_widget.setFixedSize(24, 24)
        header.addWidget(icon_widget)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(StrongBodyLabel(self.tra(title), header_content))
        if description:
            caption = CaptionLabel(self.tra(description), header_content)
            caption.setTextColor("#686868", "#aaaaaa")
            caption.setWordWrap(True)
            heading.addWidget(caption)
        header.addLayout(heading, 1)
        if collapsible:
            header.addStrut(32)
            self.chevron = IconWidget(FluentIcon.CHEVRON_RIGHT_MED, header_content)
            self.chevron.setFixedSize(16, 16)
            header.addWidget(self.chevron)
            header.addSpacing(8)

        self.body = QWidget(self)
        self.fields = QVBoxLayout(self.body)
        self.fields.setContentsMargins(20, 0, 20, 20)
        self.fields.setSpacing(12)
        self.fields.addWidget(HorizontalSeparator(self))
        layout.addWidget(self.body, 1, 0)
        if collapsible:
            self.expand_button.toggled.connect(self._set_expanded)
            self.body.hide()

    def _set_expanded(self, expanded):
        self.body.setVisible(expanded)
        self.chevron.setIcon(FluentIcon.CHEVRON_DOWN_MED if expanded else FluentIcon.CHEVRON_RIGHT_MED)
        self.expand_button.setToolTip(self.tra("收起参数") if expanded else self.tra("展开参数"))

    def add_field(self, label, widget, description="", *, multiline=False):
        row = QWidget(self.body)
        layout = QVBoxLayout(row) if multiline else QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12 if multiline else 24)
        text = QWidget(row)
        text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        text_layout = QVBoxLayout(text)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        title = BodyLabel(self.tra(label), text)
        title.setWordWrap(True)
        title.setBuddy(widget)
        text_layout.addWidget(title)
        if description:
            caption = CaptionLabel(self.tra(description), text)
            caption.setTextColor("#686868", "#aaaaaa")
            caption.setWordWrap(True)
            text_layout.addWidget(caption)
        if multiline:
            text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout.addWidget(text, 0 if multiline else 1)
        if isinstance(widget, SwitchButton):
            widget.setOnText(self.tra("开启"))
            widget.setOffText(self.tra("关闭"))
            layout.addWidget(widget, 0, Qt.AlignRight | Qt.AlignVCenter)
        elif isinstance(widget, SpinBox):
            widget.setFixedWidth(160)
            layout.addWidget(widget, 0, Qt.AlignRight | Qt.AlignVCenter)
        else:
            if not multiline:
                widget.setMinimumWidth(240)
                widget.setMaximumWidth(480)
            layout.addWidget(widget, 1)
        self.fields.addWidget(row)
