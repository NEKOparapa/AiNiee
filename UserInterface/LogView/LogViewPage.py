from collections import deque

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from qfluentwidgets import isDarkTheme, PushButton, FluentIcon

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Log.LogSystem import get_gui_handler
from UserInterface.Widget.Toast import ToastMixin


_MAX_LINES = 5000

_DARK_COLORS = {
    "CRITICAL": "#e06c75",
    "ERROR": "#e06c75",
    "WARNING": "#e5c07b",
}

_LIGHT_COLORS = {
    "CRITICAL": "#c0392b",
    "ERROR": "#c0392b",
    "WARNING": "#996600",
}


class LogViewPage(QWidget, ConfigMixin, LogMixin, ToastMixin, Base):
    line_received = pyqtSignal(str, str)

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self._buffer: deque = deque(maxlen=_MAX_LINES)
        self._auto_scroll = True

        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        font = self.text_edit.font()
        font.setFamily("Menlo, Consolas, monospace")
        self.text_edit.setFont(font)
        self.container.addWidget(self.text_edit)

        # 浮动"回到底部"按钮，用户手动向上滚后才显示
        self.scroll_btn = PushButton(self.text_edit)
        self.scroll_btn.setText("回到底部")
        self.scroll_btn.setIcon(FluentIcon.DOWN)
        self.scroll_btn.clicked.connect(self._scroll_to_bottom)
        self.scroll_btn.hide()

        self.text_edit.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self.line_received.connect(self._append_line, Qt.QueuedConnection)
        get_gui_handler().subscribe(self._on_log_line)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        btn = self.scroll_btn
        btn.adjustSize()
        margin = 16
        x = self.text_edit.width() - btn.width() - margin
        y = self.text_edit.height() - btn.height() - margin
        btn.move(x, y)

    def _on_log_line(self, line: str, level: str) -> None:
        self.line_received.emit(line, level)

    def _append_line(self, line: str, level: str) -> None:
        self._buffer.append((line, level))
        self._render_line(line, level)
        self._trim_view()
        if self._auto_scroll:
            self._scroll_to_bottom()

    def _render_line(self, line: str, level: str) -> None:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        color = palette.get(level)
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if color:
            html = f'<span style="color:{color};">{safe}</span>'
        else:
            html = safe
        self.text_edit.append(html)

    def _trim_view(self) -> None:
        doc = self.text_edit.document()
        excess = doc.blockCount() - _MAX_LINES
        if excess <= 0:
            return
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        for _ in range(excess):
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _on_scroll(self, value: int) -> None:
        scroll = self.text_edit.verticalScrollBar()
        at_bottom = value >= scroll.maximum() - 2
        self._auto_scroll = at_bottom
        self.scroll_btn.setVisible(not at_bottom)

    def _scroll_to_bottom(self) -> None:
        scroll = self.text_edit.verticalScrollBar()
        scroll.setValue(scroll.maximum())
        self._auto_scroll = True
        self.scroll_btn.hide()
