from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import CheckBox, MessageBoxBase, StrongBodyLabel

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin


class TerminologyMatchSettingsDialog(ConfigMixin, Base, MessageBoxBase):
    def __init__(self, parent=None, start_check: bool = False):
        super().__init__(parent)
        self.start_check = start_check

        self.default = {
            "prompt_dictionary_match_case_sensitive": False,
            "prompt_dictionary_match_whole_word": False,
        }
        self.config_data = self.load_config_from_default()
        self.check_params = {}

        self.view = QWidget(self)
        self.view_layout = QVBoxLayout(self.view)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.setSpacing(16)
        self.view.setMinimumWidth(360)

        self._init_ui()
        self._restore_ui_state()

        self.viewLayout.addWidget(self.view)
        self.yesButton.setText(self.tra("开始检查") if self.start_check else self.tra("确认"))
        self.cancelButton.setText(self.tra("取消"))

    def _init_ui(self) -> None:
        self.view_layout.addWidget(StrongBodyLabel(self.tra("原文匹配方式"), self))

        self.case_sensitive_checkbox = CheckBox(self.tra("大小写敏感"), self)
        self.whole_word_checkbox = CheckBox(self.tra("全词匹配"), self)

        self.view_layout.addWidget(self.case_sensitive_checkbox)
        self.view_layout.addWidget(self.whole_word_checkbox)

    def _restore_ui_state(self) -> None:
        self.case_sensitive_checkbox.setChecked(
            bool(self.config_data.get("prompt_dictionary_match_case_sensitive", False))
        )
        self.whole_word_checkbox.setChecked(
            bool(self.config_data.get("prompt_dictionary_match_whole_word", False))
        )

    def accept(self) -> None:
        config = self.load_config()
        config["prompt_dictionary_match_case_sensitive"] = self.case_sensitive_checkbox.isChecked()
        config["prompt_dictionary_match_whole_word"] = self.whole_word_checkbox.isChecked()
        self.save_config(config)
        self.config_data = config
        self.check_params = {
            "case_sensitive": self.case_sensitive_checkbox.isChecked(),
            "whole_word": self.whole_word_checkbox.isChecked(),
        }
        super().accept()
