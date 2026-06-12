import threading
from collections import deque

from PyQt5.QtCore import QUrl, QTimer
from PyQt5.QtGui import QColor, QDesktopServices, QTextCursor, QTextDocument
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit

from qfluentwidgets import isDarkTheme, PushButton, FluentIcon, ComboBox, LineEdit, qconfig

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import user_log_dir
from ModuleFolders.Infrastructure.Platform.PlatformPaths import monospace_font_family
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Log.LogSystem import get_gui_handler
from UserInterface.Widget.Toast import ToastMixin


_MAX_LINES = 5000
_MAX_HIGHLIGHTS = 500

_DARK_COLORS = {
    "CRITICAL": "#e06c75",
    "ERROR": "#e06c75",
    "WARNING": "#e5c07b",
    "ARROW": "#61afef",
    "SUCCESS": "#98c379",
}

_LIGHT_COLORS = {
    "CRITICAL": "#c0392b",
    "ERROR": "#c0392b",
    "WARNING": "#996600",
    "ARROW": "#0067c0",
    "SUCCESS": "#188038",
}

_FILTER_LEVELS = ("ALL", "INFO", "WARNING", "ERROR", "CRITICAL")
_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
_HIGHLIGHT_BG = QColor("#f1c40f")


class LogViewPage(QWidget, ConfigMixin, LogMixin, ToastMixin, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self._buffer: deque = deque(maxlen=_MAX_LINES)
        self._pending: deque = deque(maxlen=_MAX_LINES)
        self._pending_lock = threading.Lock()
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
        self.search_edit.setPlaceholderText(self.tra("搜索..."))
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
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.text_edit.setPlaceholderText(self.tra("等待日志..."))
        font = self.text_edit.font()
        font.setFamily(monospace_font_family())
        self.text_edit.setFont(font)
        self.container.addWidget(self.text_edit)

        # 浮动"回到底部"按钮
        self.scroll_btn = PushButton(self.text_edit)
        self.scroll_btn.setText(self.tra("回到底部"))
        self.scroll_btn.setIcon(FluentIcon.DOWN)
        self.scroll_btn.clicked.connect(self._scroll_to_bottom)
        self.scroll_btn.hide()

        self.text_edit.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._highlight_timer = QTimer(self)
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(200)
        self._highlight_timer.timeout.connect(self._reapply_highlight)

        # 合并渲染：worker 线程把日志塞进缓冲，由 GUI 线程定时器批量取，避免高并发洪水灌满事件队列
        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(100)
        self._drain_timer.timeout.connect(self._drain_pending)
        self._drain_timer.start()

        self._gui_handler = get_gui_handler()
        self._gui_handler.subscribe(self._on_log_line, batch_cb=self._append_batch)
        try:
            qconfig.themeChanged.connect(self._rerender_view)
        except RuntimeError:
            pass
        self.destroyed.connect(self._unsubscribe_on_destroy)

    def _unsubscribe_on_destroy(self, *_args) -> None:
        try:
            self._gui_handler.unsubscribe(self._on_log_line)
        except Exception:
            pass
        try:
            qconfig.themeChanged.disconnect(self._rerender_view)
        except (TypeError, RuntimeError):
            pass
        try:
            self._highlight_timer.stop()
        except (RuntimeError, AttributeError):
            pass
        try:
            self._drain_timer.stop()
        except (RuntimeError, AttributeError):
            pass

    def closeEvent(self, event):
        try:
            self._gui_handler.unsubscribe(self._on_log_line)
        except Exception:
            pass
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        btn = self.scroll_btn
        btn.adjustSize()
        margin = 16
        x = self.text_edit.width() - btn.width() - margin
        y = self.text_edit.height() - btn.height() - margin
        btn.move(x, y)

    def _on_log_line(self, line: str, level: str, style: str = "", rows=None) -> None:
        # 可能在 worker 线程被调用：只入缓冲，渲染交给 GUI 线程的 _drain_timer
        with self._pending_lock:
            self._pending.append((line, level, style, rows))

    def _drain_pending(self) -> None:
        with self._pending_lock:
            if not self._pending:
                return
            batch = list(self._pending)
            self._pending.clear()
        try:
            self._append_batch(batch)
        except Exception:
            return

    def _append_batch(self, history) -> None:
        self.text_edit.setUpdatesEnabled(False)
        try:
            for item in history:
                line, level, style, rows = self._unpack_log_item(item)
                self._buffer.append((line, level, style, rows))
                if self._matches_filter(level):
                    self._render_line(line, level, style, rows)
            self._trim_view()
        finally:
            self.text_edit.setUpdatesEnabled(True)
        if self._search_text:
            self._highlight_timer.start()
        if self._auto_scroll:
            self._scroll_to_bottom()

    def _matches_filter(self, level: str) -> bool:
        if self._filter_level == "ALL":
            return True
        threshold = _LEVEL_ORDER.get(self._filter_level, 0)
        return _LEVEL_ORDER.get(level, threshold) >= threshold

    @staticmethod
    def _unpack_log_item(item) -> tuple[str, str, str, object]:
        if len(item) >= 4:
            line, level, style, rows = item[:4]
        elif len(item) == 3:
            line, level, style = item
            rows = None
        else:
            line, level = item
            style = ""
            rows = None
        return line, level, style, rows

    @staticmethod
    def _escape_html(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _is_separator_line(text: str) -> bool:
        stripped = text.strip()
        return bool(stripped) and set(stripped) == {"-"}

    def _style_line(self, raw_line: str, level: str, style: str) -> str:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        color = palette.get(level)
        if self._is_separator_line(raw_line):
            if style == "error":
                color = palette["ERROR"]
            elif style == "success":
                color = palette["SUCCESS"]
        safe = self._escape_html(raw_line)
        safe = safe.replace("--&gt;", f'<span style="color:{palette["ARROW"]};">--&gt;</span>')
        if color:
            return f'<span style="color:{color}; white-space:pre;">{safe}</span>'
        return f'<span style="white-space:pre;">{safe}</span>'

    def _style_inline_text(self, text: str) -> str:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        safe = self._escape_html(text)
        return safe.replace("--&gt;", f'<font color="{palette["ARROW"]}">--&gt;</font>')

    def _table_border_color(self, style: str) -> str:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        if style == "error":
            return palette["ERROR"]
        if style == "success":
            return palette["SUCCESS"]
        return palette["WARNING"]

    def _render_table(self, rows, style: str) -> None:
        border_color = self._table_border_color(style)
        table_rows = []
        for row in rows:
            if not isinstance(row, (list, tuple)):
                row = [row]
            cells = []
            for cell in row:
                text = cell if isinstance(cell, str) else str(cell)
                lines = [self._style_inline_text(part) for part in text.split("\n")]
                cells.append(
                    '<td style="border:1px solid {0}; padding:6px; vertical-align:top;">{1}</td>'.format(
                        border_color,
                        "<br>".join(lines),
                    )
                )
            table_rows.append("<tr>" + "".join(cells) + "</tr>")
        html = (
            '<table border="1" cellspacing="0" cellpadding="6" width="100%" '
            f'style="border-color:{border_color};">'
            + "".join(table_rows)
            + "</table>"
        )
        self.text_edit.append(html)

    def _render_line(self, line: str, level: str, style: str = "", rows=None) -> None:
        if rows:
            self._render_table(rows, style)
            return
        html = "<br>".join(self._style_line(raw_line, level, style) for raw_line in line.split("\n"))
        self.text_edit.append(html)

    def _trim_view(self) -> None:
        doc = self.text_edit.document()
        excess = doc.blockCount() - _MAX_LINES
        if excess <= 0:
            return
        if self._search_text:
            self.text_edit.setExtraSelections([])
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor, excess)
        cursor.removeSelectedText()

    def _rerender_view(self) -> None:
        try:
            self.text_edit.clear()
            for item in self._buffer:
                line, level, style, rows = self._unpack_log_item(item)
                if self._matches_filter(level):
                    self._render_line(line, level, style, rows)
            self._trim_view()
            self._reapply_highlight()
            if self._auto_scroll:
                self._scroll_to_bottom()
        except RuntimeError:
            return

    def _on_filter_changed(self, text: str) -> None:
        self._filter_level = text
        self._rerender_view()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._highlight_timer.start()

    def _reapply_highlight(self) -> None:
        try:
            if not self._search_text:
                self.text_edit.setExtraSelections([])
                return
            selections = []
            doc = self.text_edit.document()
            cursor = QTextCursor(doc)
            flags = QTextDocument.FindFlags()  # case-insensitive 默认
            while len(selections) < _MAX_HIGHLIGHTS:
                cursor = doc.find(self._search_text, cursor, flags)
                if cursor.isNull():
                    break
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cursor
                sel.format.setBackground(_HIGHLIGHT_BG)
                selections.append(sel)
            self.text_edit.setExtraSelections(selections)
        except RuntimeError:
            return

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
        with self._pending_lock:
            self._pending.clear()
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
