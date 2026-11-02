"""Grouped settings fields shared by provider and task configuration pages."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel, CaptionLabel, CardWidget, FluentIcon, HorizontalSeparator,
    IconWidget, SpinBox, StrongBodyLabel, SwitchButton, TransparentToolButton,
)

from Frontend.core.config import ConfigMixin


class SettingsSection(CardWidget, ConfigMixin):
    def __init__(self, title, icon, description="", parent=None, *, collapsible=False):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)
        header = QHBoxLayout()
        header.setSpacing(12)
        icon_widget = IconWidget(icon, self)
        icon_widget.setFixedSize(24, 24)
        header.addWidget(icon_widget)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(StrongBodyLabel(self.tra(title), self))
        if description:
            caption = CaptionLabel(self.tra(description), self)
            caption.setTextColor("#686868", "#aaaaaa")
            caption.setWordWrap(True)
            heading.addWidget(caption)
        header.addLayout(heading, 1)
        layout.addLayout(header)

        self.body = QWidget(self)
        self.fields = QVBoxLayout(self.body)
        self.fields.setContentsMargins(0, 0, 0, 0)
        self.fields.setSpacing(12)
        self.fields.addWidget(HorizontalSeparator(self))
        layout.addWidget(self.body)
        if collapsible:
            self.expand_button = TransparentToolButton(FluentIcon.CHEVRON_RIGHT_MED, self)
            self.expand_button.setFixedSize(32, 32)
            self.expand_button.setCheckable(True)
            self.expand_button.setToolTip(self.tra("展开参数"))
            self.expand_button.setAccessibleName(self.tra(title))
            self.expand_button.toggled.connect(self._set_expanded)
            header.addWidget(self.expand_button)
            self.body.hide()

    def _set_expanded(self, expanded):
        self.body.setVisible(expanded)
        self.expand_button.setIcon(FluentIcon.CHEVRON_DOWN_MED if expanded else FluentIcon.CHEVRON_RIGHT_MED)
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
