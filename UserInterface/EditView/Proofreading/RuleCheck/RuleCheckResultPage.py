from PyQt5.QtWidgets import QVBoxLayout, QWidget

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.EditView.Proofreading.Common.CheckStatusPage import CheckStatusPage
from UserInterface.EditView.Proofreading.Common.EditableIssueTablePage import EditableIssueTablePage


class RuleCheckResultPage(ConfigMixin, Base, QWidget):
    def __init__(self, result_data: dict, cache_manager=None, parent=None):
        super().__init__(parent)
        self.cache_manager = cache_manager
        self.result_data = result_data
        self.setObjectName("RuleCheckResultPage")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        content_widget = self._create_content_widget()
        self.layout.addWidget(content_widget, 1)

    def _create_content_widget(self) -> QWidget:
        enabled_rules = self.result_data.get("enabled_rules", [])
        issue_rows = self.result_data.get("issue_rows", [])

        if issue_rows:
            return EditableIssueTablePage(issue_rows, self.cache_manager, self)

        if not enabled_rules:
            return CheckStatusPage(
                self.tra("未启用规则检查项"),
                self.tra("请选择至少一项规则后重新检查"),
                self,
            )

        return CheckStatusPage(
            self.tra("未发现规则问题"),
            self.tra("当前启用规则未发现异常"),
            self,
        )
