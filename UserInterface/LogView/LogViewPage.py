from collections import deque

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices, QTextCursor, QTextDocument
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit

from qfluentwidgets import isDarkTheme, PushButton, FluentIcon, ComboBox, LineEdit

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import user_log_dir
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

_FILTER_LEVELS = ("ALL", "INFO", "WARNING", "ERROR", "CRITICAL")
_HIGHLIGHT_BG = QColor("#f1c40f")


class LogViewPage(QWidget, ConfigMixin, LogMixin, ToastMixin, Base):
    line_received = pyqtSignal(str, str)

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self._buffer: deque = deque(maxlen=_MAX_LINES)
        self._auto_scroll = True
        self._filter_level = "ALL"
        self._search_text = ""

        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(8, 8, 8, 8)
        self.container.setSpacing(6)

        # 顶部 toolbar：等级过滤 + 搜索
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.level_combo = ComboBox(self)
        for lv in _FILTER_LEVELS:
            self.level_combo.addItem(lv)
        self.level_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.level_combo)

        self.search_edit = LineEdit(self)
        self.search_edit.setPlaceholderText("搜索...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_edit, stretch=1)

        self.copy_btn = PushButton(self.tra("复制全部"), self)
        self.copy_btn.setIcon(FluentIcon.COPY)
        self.copy_btn.clicked.connect(self._on_copy_all)
        toolbar.addWidget(self.copy_btn)

        self.clear_btn = PushButton(self.tra("清空"), self)
        self.clear_btn.setIcon(FluentIcon.DELETE)
        self.clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self.clear_btn)

        self.open_dir_btn = PushButton(self.tra("打开日志目录"), self)
        self.open_dir_btn.setIcon(FluentIcon.FOLDER)
        self.open_dir_btn.clicked.connect(self._on_open_dir)
        toolbar.addWidget(self.open_dir_btn)

        self.container.addLayout(toolbar)

        # 主体：等宽只读 QTextEdit
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlaceholderText(self.tra("等待日志..."))
        font = self.text_edit.font()
        font.setFamily("Menlo, Consolas, monospace")
        self.text_edit.setFont(font)
        self.container.addWidget(self.text_edit)

        # 浮动"回到底部"按钮
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
        if not self._matches_filter(level):
            return
        self._render_line(line, level)
        self._trim_view()
        self._reapply_highlight()
        if self._auto_scroll:
            self._scroll_to_bottom()

    def _matches_filter(self, level: str) -> bool:
        return self._filter_level == "ALL" or level == self._filter_level

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

    def _rerender_view(self) -> None:
        self.text_edit.clear()
        for line, level in self._buffer:
            if self._matches_filter(level):
                self._render_line(line, level)
        self._trim_view()
        self._reapply_highlight()
        if self._auto_scroll:
            self._scroll_to_bottom()

    def _on_filter_changed(self, text: str) -> None:
        self._filter_level = text
        self._rerender_view()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._reapply_highlight()

    def _reapply_highlight(self) -> None:
        if not self._search_text:
            self.text_edit.setExtraSelections([])
            return
        selections = []
        doc = self.text_edit.document()
        cursor = QTextCursor(doc)
        flags = QTextDocument.FindFlags()  # case-insensitive 默认
        while True:
            cursor = doc.find(self._search_text, cursor, flags)
            if cursor.isNull():
                break
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format.setBackground(_HIGHLIGHT_BG)
            selections.append(sel)
        self.text_edit.setExtraSelections(selections)

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

    def _on_copy_all(self) -> None:
        QApplication.clipboard().setText(self.text_edit.toPlainText())
        self.success_toast("", self.tra("已复制到剪贴板"))

    def _on_clear(self) -> None:
        self._buffer.clear()
        self.text_edit.clear()
        self.scroll_btn.hide()
        self._auto_scroll = True

    def _on_open_dir(self) -> None:
        try:
            log_dir = user_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))
            if not opened:
                self.error_toast("", self.tra("无法打开日志目录"))
        except OSError as e:
            self.error_toast("", self.tra("无法打开日志目录") + f": {e}")
