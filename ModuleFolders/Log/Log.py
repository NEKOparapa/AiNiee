import logging
import traceback

from rich import print


class LogMixin:
    @staticmethod
    def _format_exception(error: Exception) -> str:
        return "".join(traceback.format_exception(None, error, error.__traceback__)).strip()

    def _logger(self) -> logging.Logger:
        return logging.getLogger(type(self).__module__)

    def print(self, msg: str) -> None:
        print(msg)
        self._logger().info(msg)

    def debug(self, msg: str, error: Exception = None) -> None:
        if error is None:
            print(f"[[yellow]DEBUG[/]] {msg}")
            self._logger().debug(msg)
        else:
            print(f"[[yellow]DEBUG[/]] {msg}\n{error}\n{self._format_exception(error)}")
            self._logger().debug(msg, exc_info=error)

    def info(self, msg: str) -> None:
        print(f"[[green]INFO[/]] {msg}")
        self._logger().info(msg)

    def error(self, msg: str, error: Exception = None) -> None:
        if error is None:
            print(f"[[red]ERROR[/]] {msg}")
            self._logger().error(msg)
        else:
            print(f"[[red]ERROR[/]] {msg}\n{error}\n{self._format_exception(error)}")
            self._logger().error(msg, exc_info=error)

    def warning(self, msg: str) -> None:
        print(f"[[red]WARNING[/]] {msg}")
        self._logger().warning(msg)
