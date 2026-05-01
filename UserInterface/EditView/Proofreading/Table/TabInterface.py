from PyQt5.QtWidgets import QVBoxLayout, QWidget

from UserInterface.EditView.Proofreading.Table.BasicTablePage import BasicTablePage


class TabInterface(QWidget):
    def __init__(self, text: str, file_path: str, file_items: list, cache_manager, parent=None):
        super().__init__(parent=parent)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)

        self.tableView = BasicTablePage(file_path, file_items, cache_manager, self)
        self.vBoxLayout.addWidget(self.tableView)
        self.setObjectName(file_path)
