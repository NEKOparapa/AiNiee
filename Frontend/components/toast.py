from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBar
from qfluentwidgets import InfoBarPosition


class ToastMixin:
    def get_parent_window(self):
        if hasattr(self, "window"):
            if callable(self.window):
                return self.window()
            return self.window
        return None

    def _show_toast(self, toast_type: str, title: str, content: str) -> None:
        getattr(InfoBar, toast_type)(
            title=title,
            content=content,
            parent=self.get_parent_window(),
            duration=2500,
            orient=Qt.Horizontal,
            position=InfoBarPosition.TOP,
            isClosable=True,
        )

    def info_toast(self, title: str, content: str) -> None:
        self._show_toast("info", title, content)

    def error_toast(self, title: str, content: str) -> None:
        self._show_toast("error", title, content)

    def success_toast(self, title: str, content: str) -> None:
        self._show_toast("success", title, content)

    def warning_toast(self, title: str, content: str) -> None:
        self._show_toast("warning", title, content)
