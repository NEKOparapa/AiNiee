from PyQt5.QtWidgets import QVBoxLayout, QWidget

from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin
from Frontend.pages.workspace.proofreading.check_status_page import CheckStatusPage
from Frontend.pages.workspace.proofreading.editable_issue_table_page import EditableIssueTablePage


class TerminologyCheckResultPage(ConfigMixin, Base, QWidget):
    def __init__(self, result_data: dict, cache_manager=None, parent=None):
        super().__init__(parent)
        self.cache_manager = cache_manager
        self.result_data = result_data
        self.setObjectName("TerminologyCheckResultPage")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        content_widget = self._create_content_widget()
        self.layout.addWidget(content_widget, 1)

    def _create_content_widget(self) -> QWidget:
        issue_rows = self.result_data.get("issue_rows", [])

        if issue_rows:
            return EditableIssueTablePage(
                issue_rows,
                self.cache_manager,
                self,
                update_event=Base.EVENT.TABLE_TERMINOLOGY_CHECK_UPDATE,
                done_event=Base.EVENT.TABLE_TERMINOLOGY_CHECK_DONE,
            )

        return CheckStatusPage(
            self.tra("未发现术语问题"),
            self.tra("当前术语表未发现异常"),
            self,
        )
