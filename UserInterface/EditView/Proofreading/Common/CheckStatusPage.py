from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, StrongBodyLabel

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin


class CheckStatusPage(ConfigMixin, Base, QWidget):
    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("CheckStatusPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)
        layout.addStretch(1)

        self.title_label = StrongBodyLabel(title, self)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.description_label = BodyLabel(description, self)
        self.description_label.setAlignment(Qt.AlignCenter)
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        layout.addStretch(1)
