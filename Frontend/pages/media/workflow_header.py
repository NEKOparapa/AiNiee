"""Shared navigation for the media translation and proofreading views."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import CardWidget, FluentIcon, SegmentedWidget, TransparentPushButton

from Frontend.core.config import ConfigMixin


class MediaWorkflowHeader(CardWidget, ConfigMixin):
    backRequested = pyqtSignal()
    saveRequested = pyqtSignal()
    exportRequested = pyqtSignal()
    stepChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 9, 16, 9)
        layout.setSpacing(12)

        left = QWidget(self)
        right = QWidget(self)
        left_layout = QHBoxLayout(left)
        right_layout = QHBoxLayout(right)
        for side, side_layout in ((left, left_layout), (right, right_layout)):
            side.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            side_layout.setContentsMargins(0, 0, 0, 0)
            side_layout.setSpacing(8)

        self.back_button = TransparentPushButton(FluentIcon.RETURN, self.tra("返回"), left)
        self.save_button = TransparentPushButton(FluentIcon.SAVE, self.tra("保存"), right)
        self.export_button = TransparentPushButton(FluentIcon.SHARE, self.tra("导出结果"), right)
        for button in (self.back_button, self.save_button, self.export_button):
            button.setFixedHeight(32)

        left_layout.addWidget(self.back_button, 0, Qt.AlignLeft)
        left_layout.addStretch(1)
        right_layout.addStretch(1)
        right_layout.addWidget(self.save_button)
        right_layout.addWidget(self.export_button)

        self.step_widget = SegmentedWidget(self)
        self.step_widget.setFixedSize(240, 38)
        for route, label in (("translation", "翻译"), ("proofreading", "校润")):
            item = self.step_widget.addItem(
                routeKey=route,
                text=self.tra(label),
                onClick=lambda checked=False, key=route: self.stepChanged.emit(key),
            )
            item.setFixedHeight(38)

        # Equal side minima and stretch keep navigation at the card's center.
        side_minimum = max(left.minimumSizeHint().width(), right.minimumSizeHint().width())
        left.setMinimumWidth(side_minimum)
        right.setMinimumWidth(side_minimum)
        layout.addWidget(left, 1)
        layout.addWidget(self.step_widget, 0, Qt.AlignCenter)
        layout.addWidget(right, 1)

        self.back_button.clicked.connect(self.backRequested.emit)
        self.save_button.clicked.connect(self.saveRequested.emit)
        self.export_button.clicked.connect(self.exportRequested.emit)
        self.set_current_step("translation")

    def set_current_step(self, route):
        if route in ("translation", "proofreading"):
            self.step_widget.setCurrentItem(route)
