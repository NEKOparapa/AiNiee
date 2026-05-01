import traceback

from rich import print


class LogMixin:
    @staticmethod
    def _format_exception(error: Exception) -> str:
        return "".join(traceback.format_exception(None, error, error.__traceback__)).strip()

    def print(self, msg: str) -> None:
        print(msg)

    def debug(self, msg: str, error: Exception = None) -> None:
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
