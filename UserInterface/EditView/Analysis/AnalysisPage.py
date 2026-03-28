from PyQt5.QtWidgets import QWidget, QVBoxLayout

from ModuleFolders.Config.Config import ConfigMixin


class AnalysisPage(ConfigMixin, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnalysisPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.addStretch(1)
