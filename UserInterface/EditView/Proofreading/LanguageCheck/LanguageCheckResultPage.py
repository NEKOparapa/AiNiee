from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import TableWidget

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.EditView.Proofreading.Common.CheckStatusPage import CheckStatusPage
from UserInterface.EditView.Proofreading.Common.EditableIssueTablePage import EditableIssueTablePage


class LanguageReportTablePage(ConfigMixin, Base, QWidget):
    def __init__(self, report_rows: list, parent=None):
        super().__init__(parent)
        self.report_rows = report_rows
        self.setObjectName("LanguageReportTablePage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.table = TableWidget(self)
        layout.addWidget(self.table)

        self._init_table()
        self._populate_data()

    def _init_table(self):
        headers = [self.tra("文件"), self.tra("类型"), self.tra("编码"), self.tra("语言统计")]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self.table.setColumnWidth(0, 320)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 120)

    def _populate_data(self):
        self.table.setRowCount(len(self.report_rows))
        for row, data in enumerate(self.report_rows):
            file_item = QTableWidgetItem(data.get("file_path", ""))
            file_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 0, file_item)

            type_item = QTableWidgetItem(data.get("file_type", ""))
            type_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, type_item)

            encoding_item = QTableWidgetItem(data.get("encoding", ""))
            encoding_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 2, encoding_item)

            stats_item = QTableWidgetItem(data.get("stats_text", ""))
            stats_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 3, stats_item)

        self.table.resizeRowsToContents()


class LanguageCheckResultPage(ConfigMixin, Base, QWidget):
    def __init__(self, result_data: dict, cache_manager=None, parent=None):
        super().__init__(parent)
        self.cache_manager = cache_manager
        self.result_data = result_data
        self.setObjectName("LanguageCheckResultPage")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        content_widget = self._create_content_widget()
        self.layout.addWidget(content_widget, 1)

    def _create_content_widget(self) -> QWidget:
        mode = self.result_data.get("mode", "report")
        report_rows = self.result_data.get("report_rows", [])
        issue_rows = self.result_data.get("issue_rows", [])

        if mode == "report":
            return LanguageReportTablePage(report_rows, self)

        if issue_rows:
            return EditableIssueTablePage(issue_rows, self.cache_manager, self)

        return CheckStatusPage(
            self.tra("未发现语言问题"),
            self.tra("所有文件均符合目标语言预期"),
            self,
        )
