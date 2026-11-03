"""Display and select media workflow steps without starting any operations."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel, CheckBox, FluentIcon, IconWidget, SimpleCardWidget, themeColor,
)

from Frontend.core.config import ConfigMixin


class _WorkflowStep(SimpleCardWidget, ConfigMixin):
    def __init__(self, title, number, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header = QHBoxLayout(self)
        header.setContentsMargins(12, 10, 12, 10)
        header.setSpacing(8)
        self.check = CheckBox(f"{number}. {self.tra(title)}", self)
        self.check.setChecked(True)
        header.addWidget(self.check)
        header.addStretch(1)
        self.status_label = CaptionLabel(self)
        self.status_label.setTextFormat(Qt.PlainText)
        header.addWidget(self.status_label)
        self.set_state({})

    def set_state(self, state):
        active = bool(state.get("active", False))
        self.status_label.setText(str(state.get("status") or self.tra("待开始")))
        self.status_label.setToolTip(str(state.get("detail") or ""))
        self.status_label.setTextColor(
            themeColor() if active else "#707070",
            themeColor() if active else "#b0b0b0")


class MediaWorkflowSelector(QWidget, ConfigMixin):
    """Keep explicit step selections for each mode; all execution belongs to the parent."""

    selectionChanged = pyqtSignal()

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._mode = None
        self._busy = False
        self._columns = 0
        self._visible_stages = ()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(4)
        layout.addLayout(self.grid)

        definitions = (("recognize", "转录字幕"), ("translate", "翻译字幕")) if kind == "audio" else (
            ("detect", "文本检测"), ("recognize", "OCR 识别"),
            ("translate", "AI 翻译"), ("preview", "译文填回"),
            ("generate", "生成译图"),
        )
        self._cards = {}
        for index, (stage, title) in enumerate(definitions):
            card = _WorkflowStep(title, 1 if stage == "generate" else index + 1, self)
            card.check.setChecked(stage != "detect")
            card.check.toggled.connect(lambda checked: self.selectionChanged.emit())
            self._cards[stage] = card
        self._arrows = []
        for _ in range(1 if kind == "audio" else 3):
            arrow = IconWidget(FluentIcon.RIGHT_ARROW, self)
            arrow.setFixedSize(16, 16)
            arrow.setAttribute(Qt.WA_TransparentForMouseEvents)
            self._arrows.append(arrow)
        self.hint_label = CaptionLabel(self)
        self.hint_label.setTextFormat(Qt.PlainText)
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextColor("#9a5a00", "#e5b35e")
        self.hint_label.hide()
        layout.addWidget(self.hint_label)
        self.configure("ocr")

    def configure(self, mode):
        mode = "generation" if self.kind != "audio" and mode == "generation" else "ocr"
        if mode == self._mode:
            return
        self._mode = mode
        self._visible_stages = (("generate",) if mode == "generation" else
                                ("recognize", "translate") if self.kind == "audio" else
                                ("detect", "recognize", "translate", "preview"))
        self._columns = 0
        self._reflow(self.width())
        self.set_hint("")
        self.selectionChanged.emit()

    def selected_stages(self):
        return [stage for stage in self._visible_stages
                if self._cards[stage].check.isChecked()]

    def set_states(self, states):
        for stage, state in states.items():
            if stage in self._cards:
                self._cards[stage].set_state(state)

    def set_busy(self, busy):
        self._busy = bool(busy)
        for card in self._cards.values():
            card.check.setEnabled(not self._busy)

    def set_hint(self, text):
        text = str(text or "").strip()
        self.hint_label.setText(text)
        self.hint_label.setVisible(bool(text))

    def _reflow(self, width):
        count = len(self._visible_stages)
        columns = max(1, min(count, 4, (width + 28) // 244))
        if columns == self._columns:
            return
        self._columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for column in range(7):
            stretch = column < columns * 2 - 1 and column % 2 == 0
            self.grid.setColumnStretch(column, 1 if stretch else 0)
            self.grid.setColumnMinimumWidth(column, 0)
        for stage, card in self._cards.items():
            card.setVisible(stage in self._visible_stages)
        for index, arrow in enumerate(self._arrows):
            arrow.setVisible(index < count - 1 and (columns == 1 or (index + 1) % columns != 0))
            arrow.setIcon(FluentIcon.RIGHT_ARROW if columns > 1 else FluentIcon.ARROW_DOWN)
        for index, stage in enumerate(self._visible_stages):
            row, column = (index // columns * 2, index % columns * 2)
            self.grid.addWidget(self._cards[stage], row, column)
            if index < count - 1 and (columns == 1 or (index + 1) % columns != 0):
                row, column = (row, column + 1) if columns > 1 else (row + 1, 0)
                self.grid.addWidget(self._arrows[index], row, column, Qt.AlignCenter)
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow(event.size().width())
