import logging
import re
import traceback
from io import StringIO

from rich import print
from rich.console import Console
from rich.markup import escape
from rich.text import Text

from ModuleFolders.Log import LogSystem as _log_system
from ModuleFolders.Log.LogSystem import redact

__all__ = ("LogMixin",)


_RICH_LOG_WIDTH = 100
_TABLE_BORDER_RE = re.compile(r"^\s*\+[-+]+\s*$")


def _rich_print(*args, **kwargs):
    """rich.print 包裹：进 print 前 depth+1，退出 -1。_BroadcastStream 看 depth>0 跳 logger.log。
    用计数器而非布尔，正确处理嵌套 rich.print 场景（避免内层 finally 提早清零外层标记）。
    rich.print 抛异常（终端 detach、format 出错 等）也吞掉，保证后续 self._logger().xxx
    仍能跑到——否则刚好在出问题时 file/GUI 日志一起丢。"""
    flag = _log_system._in_log_mixin
    flag.depth = getattr(flag, "depth", 0) + 1
    try:
        try:
            print(*args, **kwargs)
        except Exception:
            pass
    finally:
        flag.depth -= 1


def _safe_str(value) -> str:
    try:
        return str(value)
    except Exception:
        return f"<unprintable {type(value).__name__}>"


def _is_rich_renderable(value) -> bool:
    return hasattr(value, "__rich_console__") or hasattr(value, "__rich__")


def _render_rich(value) -> str:
    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=False,
        color_system=None,
        width=_RICH_LOG_WIDTH,
    )
    console.print(value)
    return buffer.getvalue().rstrip()


def _console_text(value) -> str:
    return escape(_safe_str(value))


def _log_text(value) -> str:
    if isinstance(value, str):
        return value
    if _is_rich_renderable(value):
        try:
            return _render_rich(value)
        except Exception:
            return _safe_str(value)
    return _safe_str(value)


def _gui_text_from_rich(text: str) -> str:
    """把终端表格转成 GUI 友好的文本块，避免 Qt 中 CJK 字宽导致右边框错位。"""
    lines = []
    previous_separator = False
    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if _TABLE_BORDER_RE.match(line):
            if not previous_separator:
                lines.append("-" * min(len(line.strip()), _RICH_LOG_WIDTH))
            previous_separator = True
            continue
        previous_separator = False
        if line.startswith("|"):
            line = line[1:]
            if line.rstrip().endswith("|"):
                line = line.rstrip()[:-1]
        lines.append(line.strip())
    return "\n".join(lines)


def _gui_style_from_rich(value) -> str:
    border_style = getattr(value, "border_style", "")
    if border_style == "red":
        return "error"
    if border_style == "green":
        return "success"
    return ""


def _plain_markup(value) -> str:
    text = _safe_str(value)
    try:
        return Text.from_markup(text).plain
    except Exception:
        return text


def _gui_rows_from_rich_table(value):
    columns = getattr(value, "columns", None)
    if not columns:
        return None
    cells_by_column = [list(getattr(column, "cells", ())) for column in columns]
    if not cells_by_column:
        return None
    row_count = max((len(cells) for cells in cells_by_column), default=0)
    if row_count <= 0:
        return None
    rows = []
    for row_index in range(row_count):
        row = []
        for cells in cells_by_column:
            cell = cells[row_index] if row_index < len(cells) else ""
            row.append(redact(_plain_markup(cell)))
        rows.append(row)
    return rows


def _prepare_message(value):
    text = redact(_log_text(value))
    gui_text = _gui_text_from_rich(text) if _is_rich_renderable(value) else text
    gui_style = _gui_style_from_rich(value) if _is_rich_renderable(value) else ""
    gui_rows = _gui_rows_from_rich_table(value) if _is_rich_renderable(value) else None
    return _console_text(text), text, gui_text, gui_style, gui_rows


def _log_extra(gui_text: str, gui_style: str = "", gui_rows=None) -> dict:
    return {
        "ainiee_gui_text": gui_text,
        "ainiee_gui_style": gui_style,
        "ainiee_gui_rows": gui_rows,
    }


def _with_gui_prefix(prefix: str, gui_text: str) -> str:
    if not gui_text:
        return prefix
    return f"{prefix} {gui_text}"


class LogMixin:
    @staticmethod
    def _format_exception(error: Exception) -> str:
        return "".join(traceback.format_exception(None, error, error.__traceback__)).strip()

    def _logger(self) -> logging.Logger:
        cls = type(self)
        return logging.getLogger(f"{cls.__module__}.{cls.__name__}")

    @staticmethod
    def _safe_str(value) -> str:
        return _safe_str(value)

    def print(self, msg) -> None:
        console_value, text, gui_text, gui_style, gui_rows = _prepare_message(msg)
        _rich_print(console_value, soft_wrap=True)
        self._logger().info(text, extra=_log_extra(gui_text, gui_style, gui_rows))

    def debug(self, msg, error: Exception = None) -> None:
        console_value, text, gui_text, gui_style, gui_rows = _prepare_message(msg)
        gui_text = _with_gui_prefix("[DEBUG]", gui_text)
        if error is None:
            _rich_print(f"[[yellow]DEBUG[/]] {console_value}")
            self._logger().debug(text, extra=_log_extra(gui_text, gui_style, gui_rows))
        else:
            safe_tb = redact(self._format_exception(error))
            _rich_print(
                f"[[yellow]DEBUG[/]] {console_value}\n"
                f"{_console_text(redact(self._safe_str(error)))}\n"
                f"{_console_text(safe_tb)}"
            )
            self._logger().debug(text, exc_info=error, extra=_log_extra(gui_text, gui_style, gui_rows))

    def info(self, msg) -> None:
        console_value, text, gui_text, gui_style, gui_rows = _prepare_message(msg)
        gui_text = _with_gui_prefix("[INFO]", gui_text)
        _rich_print(f"[[green]INFO[/]] {console_value}")
        self._logger().info(text, extra=_log_extra(gui_text, gui_style, gui_rows))

    def error(self, msg, error: Exception = None) -> None:
        console_value, text, gui_text, gui_style, gui_rows = _prepare_message(msg)
        gui_text = _with_gui_prefix("[ERROR]", gui_text)
        if error is None:
            _rich_print(f"[[red]ERROR[/]] {console_value}")
            self._logger().error(text, extra=_log_extra(gui_text, gui_style, gui_rows))
        else:
            safe_tb = redact(self._format_exception(error))
            _rich_print(
                f"[[red]ERROR[/]] {console_value}\n"
                f"{_console_text(redact(self._safe_str(error)))}\n"
                f"{_console_text(safe_tb)}"
            )
            self._logger().error(text, exc_info=error, extra=_log_extra(gui_text, gui_style, gui_rows))

    def warning(self, msg) -> None:
        console_value, text, gui_text, gui_style, gui_rows = _prepare_message(msg)
        gui_text = _with_gui_prefix("[WARNING]", gui_text)
        _rich_print(f"[[yellow]WARNING[/]] {console_value}")
        self._logger().warning(text, extra=_log_extra(gui_text, gui_style, gui_rows))
