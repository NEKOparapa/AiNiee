import os
import traceback

from rich import print


class LogMixin:
    _is_debug = None

    @staticmethod
    def _format_exception(error: Exception) -> str:
        return "".join(traceback.format_exception(None, error, error.__traceback__)).strip()

    def is_debug(self) -> bool:
        if LogMixin._is_debug is None:
            debug_path = os.path.join(".", "debug.txt")
            LogMixin._is_debug = os.path.isfile(debug_path)

        return LogMixin._is_debug

    def reset_debug(self) -> None:
        LogMixin._is_debug = None

    def print(self, msg: str) -> None:
        print(msg)

    def debug(self, msg: str, error: Exception = None) -> None:
        if self.is_debug() is False:
            return None

        if error is None:
            print(f"[[yellow]DEBUG[/]] {msg}")
        else:
            print(f"[[yellow]DEBUG[/]] {msg}\n{error}\n{self._format_exception(error)}")

    def info(self, msg: str) -> None:
        print(f"[[green]INFO[/]] {msg}")

    def error(self, msg: str, error: Exception = None) -> None:
        if error is None:
            print(f"[[red]ERROR[/]] {msg}")
        else:
            print(f"[[red]ERROR[/]] {msg}\n{error}\n{self._format_exception(error)}")

    def warning(self, msg: str) -> None:
        print(f"[[red]WARNING[/]] {msg}")
