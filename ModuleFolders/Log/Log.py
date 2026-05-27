import logging
import traceback

from rich import print

from ModuleFolders.Log.LogSystem import redact

__all__ = ("LogMixin",)


class LogMixin:
    @staticmethod
    def _format_exception(error: Exception) -> str:
        return "".join(traceback.format_exception(None, error, error.__traceback__)).strip()

    def _logger(self) -> logging.Logger:
        cls = type(self)
        return logging.getLogger(f"{cls.__module__}.{cls.__name__}")

    @staticmethod
    def _safe_str(value) -> str:
        try:
            return str(value)
        except Exception:
            return f"<unprintable {type(value).__name__}>"

    def print(self, msg) -> None:
        safe = redact(msg)
        print(safe)
        self._logger().info(safe if isinstance(safe, str) else self._safe_str(safe))

    def debug(self, msg, error: Exception = None) -> None:
        safe = redact(msg)
        if error is None:
            print(f"[[yellow]DEBUG[/]] {safe}")
            self._logger().debug(safe if isinstance(safe, str) else self._safe_str(safe))
        else:
            safe_tb = redact(self._format_exception(error))
            print(f"[[yellow]DEBUG[/]] {safe}\n{redact(self._safe_str(error))}\n{safe_tb}")
            self._logger().debug(safe if isinstance(safe, str) else self._safe_str(safe), exc_info=error)

    def info(self, msg) -> None:
        safe = redact(msg)
        print(f"[[green]INFO[/]] {safe}")
        self._logger().info(safe if isinstance(safe, str) else self._safe_str(safe))

    def error(self, msg, error: Exception = None) -> None:
        safe = redact(msg)
        if error is None:
            print(f"[[red]ERROR[/]] {safe}")
            self._logger().error(safe if isinstance(safe, str) else self._safe_str(safe))
        else:
            safe_tb = redact(self._format_exception(error))
            print(f"[[red]ERROR[/]] {safe}\n{redact(self._safe_str(error))}\n{safe_tb}")
            self._logger().error(safe if isinstance(safe, str) else self._safe_str(safe), exc_info=error)

    def warning(self, msg) -> None:
        safe = redact(msg)
        print(f"[[red]WARNING[/]] {safe}")
        self._logger().warning(safe if isinstance(safe, str) else self._safe_str(safe))
