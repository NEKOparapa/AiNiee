from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Log.LogSystem import get_gui_handler
from UserInterface.Widget.Toast import ToastMixin


class LogViewPage(QWidget, ConfigMixin, LogMixin, ToastMixin, Base):
    line_received = pyqtSignal(str, str)

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.container.addWidget(self.text_edit)

        self.line_received.connect(self._append_line, Qt.QueuedConnection)
        get_gui_handler().subscribe(self._on_log_line)

    def _on_log_line(self, line: str, level: str) -> None:
        self.line_received.emit(line, level)

    def _append_line(self, line: str, level: str) -> None:
        self.text_edit.append(line)
