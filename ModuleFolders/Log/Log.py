import logging
import traceback
from io import StringIO

from rich import print
from rich.console import Console
from rich.markup import escape

from ModuleFolders.Log import LogSystem as _log_system
from ModuleFolders.Log.LogSystem import redact

__all__ = ("LogMixin",)


_RICH_LOG_WIDTH = 100


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


def _prepare_message(value):
    text = redact(_log_text(value))
    return _console_text(text), text


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
        console_value, text = _prepare_message(msg)
        _rich_print(console_value)
        self._logger().info(text)

    def debug(self, msg, error: Exception = None) -> None:
        console_value, text = _prepare_message(msg)
        if error is None:
            _rich_print(f"[[yellow]DEBUG[/]] {console_value}")
            self._logger().debug(text)
        else:
            safe_tb = redact(self._format_exception(error))
            _rich_print(
                f"[[yellow]DEBUG[/]] {console_value}\n"
                f"{_console_text(redact(self._safe_str(error)))}\n"
                f"{_console_text(safe_tb)}"
            )
            self._logger().debug(text, exc_info=error)

    def info(self, msg) -> None:
        console_value, text = _prepare_message(msg)
        _rich_print(f"[[green]INFO[/]] {console_value}")
        self._logger().info(text)

    def error(self, msg, error: Exception = None) -> None:
        console_value, text = _prepare_message(msg)
        if error is None:
            _rich_print(f"[[red]ERROR[/]] {console_value}")
            self._logger().error(text)
        else:
            safe_tb = redact(self._format_exception(error))
            _rich_print(
                f"[[red]ERROR[/]] {console_value}\n"
                f"{_console_text(redact(self._safe_str(error)))}\n"
                f"{_console_text(safe_tb)}"
            )
            self._logger().error(text, exc_info=error)

    def warning(self, msg) -> None:
        console_value, text = _prepare_message(msg)
        _rich_print(f"[[yellow]WARNING[/]] {console_value}")
        self._logger().warning(text)
