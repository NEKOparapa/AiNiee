import re
import threading
from collections import deque

from PyQt5 import sip
from PyQt5.QtCore import QUrl, QTimer, Qt
from PyQt5.QtGui import QColor, QDesktopServices, QPalette, QTextCursor, QTextDocument, QTextOption, QTextTable
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit

from qfluentwidgets import isDarkTheme, PushButton, FluentIcon, ComboBox, LineEdit, qconfig

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import user_log_dir
from ModuleFolders.Infrastructure.Platform.PlatformPaths import monospace_font_family
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Log.LogSystem import get_gui_handler
from UserInterface.Widget.Toast import ToastMixin


_MAX_LINES = 2000
_MAX_RECORDS = 200
_MAX_HIGHLIGHTS = 500
_PROGRESS_BAR_SIZE = 6
_TASK_LOG_SPACING_PX = 40

_DARK_COLORS = {
    "SURFACE": "#11161d",
    "TEXT": "#d7dde5",
    "BORDER": "#2f3642",
    "INFO": "#9fb3c8",
    "DEBUG": "#8a9bb0",
    "CRITICAL": "#e58a84",
    "ERROR": "#e58a84",
    "WARNING": "#d1b06a",
    "ARROW": "#8fb7d8",
    "SUCCESS": "#84b5a5",
    "PATH": "#aeb8d6",
    "URL": "#8fc9d0",
    "NUMBER": "#91b7a4",
    "TIP": "#d1b06a",
    "PROGRESS": "#7fa3cc",
    "PROGRESS_BG": "#2b333e",
    "MUTED": "#9aa6b2",
    "SCROLLBAR_TRACK": "rgba(255, 255, 255, 0)",
    "SCROLLBAR_THUMB": "#3f4856",
    "SCROLLBAR_THUMB_HOVER": "#566273",
    "SELECTION_BG": "#314763",
    "SELECTION_TEXT": "#f4f7fb",
}

_LIGHT_COLORS = {
    "SURFACE": "#fbfcfe",
    "TEXT": "#24292f",
    "BORDER": "#d0d7de",
    "INFO": "#38556b",
    "DEBUG": "#596a7a",
    "CRITICAL": "#a33b34",
    "ERROR": "#a33b34",
    "WARNING": "#7a5a12",
    "ARROW": "#2f658c",
    "SUCCESS": "#3f7465",
    "PATH": "#5f668f",
    "URL": "#2c7480",
    "NUMBER": "#3f7465",
    "TIP": "#7a5a12",
    "PROGRESS": "#527da3",
    "PROGRESS_BG": "#e1e6ed",
    "MUTED": "#667280",
    "SCROLLBAR_TRACK": "rgba(255, 255, 255, 0)",
    "SCROLLBAR_THUMB": "#c7ced8",
    "SCROLLBAR_THUMB_HOVER": "#aeb8c6",
    "SELECTION_BG": "#bfd7f5",
    "SELECTION_TEXT": "#1f2328",
}

_FILTER_LEVELS = ("ALL", "INFO", "WARNING", "ERROR", "CRITICAL")
_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
_HIGHLIGHT_BG = QColor("#f1c40f")
_INLINE_TOKEN_RE = re.compile(
    r"https?://[^\s<>()]+"
    r"|/(?:[^\s<>()]+/?)+"
    r"|\[(?:INFO|DEBUG|WARNING|ERROR|CRITICAL)\]"
    r"|Tips:"
    r"|-->"
    r"|\b\d+(?:\.\d+)+(?:\s*(?:ms|dev))?\b"
)
_TQDM_PROGRESS_RE = re.compile(
    r"^\s*(?P<label>.+?):\s*(?P<percent>\d{1,3})%\|(?P<bar>[^|]*)\|\s*(?P<detail>.*)$"
)
_RICH_PROGRESS_RE = re.compile(
    r"^\s*(?P<label>.*?)\s+━+\s+(?P<percent>\d{1,3})%\s+(?P<detail>.*)$"
)


class LogViewPage(QWidget, ConfigMixin, LogMixin, ToastMixin, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 一条日志记录可能是包含上百行的富文本表格，不能把“记录数”误当成
        # “显示行数”。记录缓冲和 QTextDocument 行数分别限流。
        self._buffer: deque = deque(maxlen=_MAX_RECORDS)
        self._pending: deque = deque(maxlen=_MAX_RECORDS)
        self._pending_lock = threading.Lock()
        self._auto_scroll = True
        self._filter_level = "ALL"
        self._search_text = ""
        self._rerender_pending = False
        self._last_progress_key = ""
        self._progress_detail_lines: dict[str, set[str]] = {}
        self._progress_tables: dict[int, QTextTable] = {}

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
        self.text_edit.document().setMaximumBlockCount(_MAX_LINES)
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_edit.setWordWrapMode(QTextOption.WrapAnywhere)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setPlaceholderText(self.tra("等待日志..."))
        font = self.text_edit.font()
        font.setFamily(monospace_font_family())
        self.text_edit.setFont(font)
        self._apply_text_edit_theme()
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
            qconfig.themeChanged.connect(self._schedule_rerender_view)
            qconfig.themeChangedFinished.connect(self._schedule_rerender_view)
        except RuntimeError:
            pass
        self.destroyed.connect(self._unsubscribe_on_destroy)

    def _unsubscribe_on_destroy(self, *_args) -> None:
        try:
            self._gui_handler.unsubscribe(self._on_log_line)
        except Exception:
            pass
        try:
            qconfig.themeChanged.disconnect(self._schedule_rerender_view)
        except (TypeError, RuntimeError):
            pass
        try:
            qconfig.themeChangedFinished.disconnect(self._schedule_rerender_view)
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
        # 同一批次可能多次更新同一进度。保留最初记录的身份，只渲染最终值，
        # 并按缓冲中的顺序插入新记录，避免把进度移到后续日志之后。
        changes = {}
        should_rerender = False
        for item in history:
            result, stored_item, replaced_item = self._store_log_item(item)
            if result == "replaced":
                previous_change = changes.pop(id(replaced_item), None)
                original_item = previous_change[1] if previous_change else replaced_item
                changes[id(stored_item)] = (stored_item, original_item)
                if original_item is not None:
                    # 日志等级变化导致可见性变化时，按新的筛选结果重新排布。
                    should_rerender |= self._matches_filter(original_item[1]) != self._matches_filter(stored_item[1])
            elif result == "appended" and stored_item is not None:
                changes[id(stored_item)] = (stored_item, None)
        auto_scroll = self._auto_scroll
        scroll = self.text_edit.verticalScrollBar()
        scroll_value = scroll.value()
        scroll_signals_blocked = scroll.blockSignals(True)
        self.text_edit.setUpdatesEnabled(False)
        try:
            if should_rerender:
                self._rerender_view()
            else:
                for item in self._buffer:
                    change = changes.get(id(item))
                    if change is None:
                        continue
                    original_item = change[1]
                    line, level, style, rows = self._unpack_log_item(item)
                    if not self._matches_filter(level):
                        continue
                    if original_item is None:
                        table = self._render_line(line, level, style, rows)
                    else:
                        table = self._progress_tables.pop(id(original_item), None)
                        # 被显示行数上限裁掉的进度不应重新出现在日志末尾。
                        if table is None or sip.isdeleted(table):
                            continue
                        table = self._render_progress(line, table)
                    if table is not None:
                        self._progress_tables[id(item)] = table
                self._trim_view()
                retained_ids = {id(item) for item in self._buffer}
                self._progress_tables = {
                    key: table for key, table in self._progress_tables.items()
                    if key in retained_ids and not sip.isdeleted(table)
                }
        finally:
            self.text_edit.setUpdatesEnabled(True)
            scroll.blockSignals(scroll_signals_blocked)
        if self._search_text:
            self._highlight_timer.start()
        if auto_scroll:
            self._scroll_to_bottom()
        else:
            scroll.setValue(scroll_value)
            self._auto_scroll = False

    def _store_log_item(self, item) -> tuple[str, tuple | None, tuple | None]:
        line, level, style, rows = self._unpack_log_item(item)
        if rows:
            stored_item = (line, level, style, rows)
            self._buffer.append(stored_item)
            self._last_progress_key = ""
            return "appended", stored_item, None
        line = line.replace("\r", "").rstrip()
        if not line.strip():
            return "skipped", None, None
        stored_item = (line, level, style, rows)
        progress = self._match_progress(line) if "\n" not in line else None
        if progress is not None:
            label, percent, _detail = progress
            replace_index = self._find_progress_index(label, percent)
            self._last_progress_key = label
            if replace_index is not None:
                replaced_item = self._buffer[replace_index]
                self._buffer[replace_index] = stored_item
                return "replaced", stored_item, replaced_item
            self._progress_detail_lines[label] = set()
            self._buffer.append(stored_item)
            return "appended", stored_item, None
        if self._last_progress_key and self._is_progress_detail_line(line):
            detail_key = self._normalize_progress_detail(line)
            seen = self._progress_detail_lines.setdefault(self._last_progress_key, set())
            if detail_key in seen:
                return "skipped", None, None
            seen.add(detail_key)
            self._buffer.append(stored_item)
            return "appended", stored_item, None
        self._last_progress_key = ""
        self._buffer.append(stored_item)
        return "appended", stored_item, None

    def _find_progress_index(self, label: str, percent: int) -> int | None:
        for index in range(len(self._buffer) - 1, -1, -1):
            line, _level, _style, rows = self._unpack_log_item(self._buffer[index])
            if rows or "\n" in line:
                continue
            progress = self._match_progress(line)
            if progress is None:
                continue
            existing_label, existing_percent, _detail = progress
            if existing_label != label:
                continue
            if existing_percent < 100 or percent >= 100:
                return index
            return None
        return None

    @staticmethod
    def _normalize_progress_detail(line: str) -> str:
        return re.sub(r"\s+", " ", line.strip())

    @staticmethod
    def _is_progress_detail_line(line: str) -> bool:
        return line.strip().startswith("目标文件 ->")

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

    @staticmethod
    def _inline_token_key(token: str) -> str:
        if token.startswith("[") and token.endswith("]"):
            return token[1:-1]
        if token.startswith("http://") or token.startswith("https://"):
            return "URL"
        if token.startswith("/"):
            return "PATH"
        if token == "-->":
            return "ARROW"
        if token == "Tips:":
            return "TIP"
        return "NUMBER"

    def _highlight_inline(self, text: str) -> str:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        parts = []
        pos = 0
        for match in _INLINE_TOKEN_RE.finditer(text):
            if match.start() > pos:
                parts.append(self._escape_html(text[pos:match.start()]))
            token = match.group(0)
            color = palette.get(self._inline_token_key(token))
            safe = self._escape_html(token)
            if color:
                parts.append(f'<span style="color:{color}; font-weight:600;">{safe}</span>')
            else:
                parts.append(safe)
            pos = match.end()
        if pos < len(text):
            parts.append(self._escape_html(text[pos:]))
        return "".join(parts)

    def _style_line(self, raw_line: str, level: str, style: str) -> str:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        color = palette.get(level) if level in ("WARNING", "ERROR", "CRITICAL") else None
        has_level_prefix = raw_line.startswith(("[INFO]", "[DEBUG]", "[WARNING]", "[ERROR]", "[CRITICAL]"))
        if has_level_prefix:
            color = None
        if self._is_separator_line(raw_line):
            if style == "error":
                color = palette["ERROR"]
            elif style == "success":
                color = palette["SUCCESS"]
        safe = self._highlight_inline(raw_line)
        color = color or palette["TEXT"]
        return f'<span style="color:{color}; white-space:pre;">{safe}</span>'

    def _style_inline_text(self, text: str) -> str:
        return self._highlight_inline(text)

    def _table_border_color(self, style: str) -> str:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        if style == "error":
            return palette["ERROR"]
        if style == "success":
            return palette["SUCCESS"]
        return palette["WARNING"]

    def _render_table(self, rows, style: str) -> None:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
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
                    '<td style="border:1px solid {0}; color:{1}; padding:6px; vertical-align:top;">{2}</td>'.format(
                        border_color,
                        palette["TEXT"],
                        "<br>".join(lines),
                    )
                )
            table_rows.append("<tr>" + "".join(cells) + "</tr>")
        html = (
            '<table border="1" cellspacing="0" cellpadding="6" width="100%" '
            f'style="border-color:{border_color};">'
            + "".join(table_rows)
            + "</table>"
            + (
                '<p style="margin:0; padding:0; font-size:{0}px; '
                'line-height:{0}px;">&nbsp;</p>'
            ).format(_TASK_LOG_SPACING_PX)
        )
        self.text_edit.append(html)

    def _match_progress(self, line: str):
        text = line.replace("\r", "").strip()
        match = _TQDM_PROGRESS_RE.match(text) or _RICH_PROGRESS_RE.match(text)
        if not match:
            return None
        percent = min(max(int(match.group("percent")), 0), 100)
        label = match.group("label").strip()
        detail = match.group("detail").strip()
        return label, percent, detail

    def _render_progress(self, line: str, table: QTextTable | None = None) -> QTextTable | None:
        progress = self._match_progress(line)
        if progress is None:
            return None
        label, percent, detail = progress
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        filled = percent
        empty = 100 - percent
        detail_text = f"{percent}%"
        if detail:
            detail_text += f"  {detail}"
        bar_cells = []
        if filled:
            bar_cells.append(
                '<td width="{0}%" bgcolor="{1}" style="font-size:{2}px; line-height:{2}px;">&nbsp;</td>'.format(
                    filled,
                    palette["PROGRESS"],
                    _PROGRESS_BAR_SIZE,
                )
            )
        if empty:
            bar_cells.append(
                '<td width="{0}%" bgcolor="{1}" style="font-size:{2}px; line-height:{2}px;">&nbsp;</td>'.format(
                    empty,
                    palette["PROGRESS_BG"],
                    _PROGRESS_BAR_SIZE,
                )
            )
        bar_html = '<table border="0" cellspacing="0" cellpadding="0" width="100%"><tr>{}</tr></table>'.format(
            "".join(bar_cells)
        )
        html = (
            '<table border="0" cellspacing="0" cellpadding="0" width="100%">'
            "<tr>"
            '<td style="white-space:normal;">'
            '<span style="color:{text}; font-weight:600;">{label}</span> '
            '<span style="color:{muted};">{detail}</span>'
            "</td>"
            "</tr>"
            "<tr>"
            '<td style="font-size:{bar_size}px; line-height:{bar_size}px;">{bar}</td>'
            "</tr>"
            "</table>"
        ).format(
            label=self._escape_html(label),
            bar=bar_html,
            bar_size=_PROGRESS_BAR_SIZE,
            text=palette["TEXT"],
            muted=palette["MUTED"],
            detail=self._escape_html(detail_text),
        )
        cursor = QTextCursor(self.text_edit.document())
        if table is None:
            self.text_edit.append(html)
            cursor.movePosition(QTextCursor.End)
            cursor.movePosition(QTextCursor.PreviousCharacter)
        else:
            # 进度条包含嵌套表格，必须替换整个外层 QTextTable；只选一个
            # QTextBlock 会留下旧的进度条。历史翻译表格无需再次解析和插入。
            start = table.firstPosition() - 1
            cursor.setPosition(start)
            cursor.setPosition(table.lastPosition() + 1, QTextCursor.KeepAnchor)
            cursor.insertHtml(html)
            cursor.setPosition(start + 1)
        return cursor.currentTable()

    def _render_line(self, line: str, level: str, style: str = "", rows=None) -> QTextTable | None:
        if rows:
            self._render_table(rows, style)
            return
        if "\n" not in line:
            table = self._render_progress(line)
            if table is not None:
                return table
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

    def _schedule_rerender_view(self, *_args) -> None:
        if self._rerender_pending:
            return
        self._rerender_pending = True
        QTimer.singleShot(0, self._rerender_view)

    def _apply_text_edit_theme(self) -> None:
        palette = _DARK_COLORS if isDarkTheme() else _LIGHT_COLORS
        widget_palette = self.text_edit.palette()
        widget_palette.setColor(QPalette.Base, QColor(palette["SURFACE"]))
        widget_palette.setColor(QPalette.Text, QColor(palette["TEXT"]))
        self.text_edit.setPalette(widget_palette)
        self.text_edit.document().setDefaultStyleSheet(
            f"body {{ background-color: {palette['SURFACE']}; color: {palette['TEXT']}; }}"
        )
        self.text_edit.setStyleSheet(
            "QTextEdit {"
            f" background-color: {palette['SURFACE']};"
            f" color: {palette['TEXT']};"
            f" border: 1px solid {palette['BORDER']};"
            " border-radius: 2px;"
            " padding: 6px;"
            "}"
            "QTextEdit:focus {"
            f" border: 1px solid {palette['BORDER']};"
            "}"
            "QTextEdit QScrollBar {"
            f" background: {palette['SCROLLBAR_TRACK']};"
            "}"
            "QTextEdit QScrollBar:vertical {"
            f" background: {palette['SCROLLBAR_TRACK']};"
            " border: none;"
            " width: 10px;"
            " margin: 4px 2px 4px 2px;"
            "}"
            "QTextEdit QScrollBar::handle:vertical {"
            f" background: {palette['SCROLLBAR_THUMB']};"
            " border: none;"
            " border-radius: 3px;"
            " min-height: 36px;"
            "}"
            "QTextEdit QScrollBar::handle:vertical:hover {"
            f" background: {palette['SCROLLBAR_THUMB_HOVER']};"
            "}"
            "QTextEdit QScrollBar::add-line:vertical,"
            "QTextEdit QScrollBar::sub-line:vertical {"
            " border: none;"
            " background: transparent;"
            " height: 0px;"
            "}"
            "QTextEdit QScrollBar::add-page:vertical,"
            "QTextEdit QScrollBar::sub-page:vertical {"
            " background: transparent;"
            "}"
            "QTextEdit {"
            f" selection-background-color: {palette['SELECTION_BG']};"
            f" selection-color: {palette['SELECTION_TEXT']};"
            "}"
        )

    def _rerender_view(self) -> None:
        self._rerender_pending = False
        try:
            self._apply_text_edit_theme()
            self._progress_tables.clear()
            self.text_edit.clear()
            for item in self._buffer:
                line, level, style, rows = self._unpack_log_item(item)
                if self._matches_filter(level):
                    table = self._render_line(line, level, style, rows)
                    if table is not None:
                        self._progress_tables[id(item)] = table
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
        self._last_progress_key = ""
        self._progress_detail_lines.clear()
        self._progress_tables.clear()
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
