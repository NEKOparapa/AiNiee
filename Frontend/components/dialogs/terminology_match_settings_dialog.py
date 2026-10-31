from PyQt5.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, CheckBox, MessageBoxBase, StrongBodyLabel

from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin
from Frontend.services.editor import TableConfigHelper


class TerminologyMatchSettingsDialog(ConfigMixin, Base, MessageBoxBase):
    def __init__(self, parent=None, start_check: bool = False, match_options: dict | None = None):
        super().__init__(parent)
        self.start_check = start_check

        self.match_options = TableConfigHelper.normalize_match_options(match_options)
        if self.start_check:
            config = self.load_config()
            self.match_options = {
                "case_sensitive": bool(config.get("prompt_dictionary_match_case_sensitive", False)),
                "whole_word": bool(config.get("prompt_dictionary_match_whole_word", False)),
            }
        self.check_params = {}

        self.view = QWidget(self)
        self.view_layout = QVBoxLayout(self.view)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.setSpacing(16)
        self.view.setMinimumWidth(440)
        self.view.setMaximumWidth(520)

        self._init_ui()
        self._restore_ui_state()

        self.viewLayout.addWidget(self.view)
        self.yesButton.setText(self.tra("开始检查") if self.start_check else self.tra("确认"))
        self.cancelButton.setText(self.tra("取消"))

    def _init_ui(self) -> None:
        title = "项目分析表的原文匹配方式" if self.start_check else "原文匹配方式"
        self.view_layout.addWidget(StrongBodyLabel(self.tra(title), self))

        self.match_options_note_label = CaptionLabel(
            self.tra(
                "公共术语表使用各表自己的匹配设置；以下选项仅用于项目分析中的角色表和术语表。"
                if self.start_check else "以下选项仅对未启用正则的术语生效。"
            ),
            self,
        )
        self.match_options_note_label.setWordWrap(True)

        self.view_layout.addWidget(self.match_options_note_label)
        self.case_sensitive_checkbox = self._add_match_option(
            "大小写敏感",
            "开启后区分大小写，如 John 不匹配 john；关闭后忽略大小写。",
        )
        self.whole_word_checkbox = self._add_match_option(
            "全词匹配",
            "仅匹配完整单词，如 Ann 不匹配 Anna。建议用于英文。",
        )
        if not self.start_check:
            self.split_match_checkbox = self._add_match_option(
                "拆分匹配",
                "按空格、间隔点拆分原文，任一部分命中即引用完整条目，如 John 或 Smith 均可匹配 John Smith。普通多词术语也会拆分，可配合全词匹配使用。",
            )

    def _add_match_option(self, title: str, description: str) -> CheckBox:
        option = QWidget(self.view)
        layout = QVBoxLayout(option)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        checkbox = CheckBox(self.tra(title), option)
        description_label = CaptionLabel(self.tra(description), option)
        description_label.setWordWrap(True)
        description_label.setContentsMargins(28, 0, 0, 0)
        layout.addWidget(checkbox)
        layout.addWidget(description_label)
        self.view_layout.addWidget(option)
        return checkbox

    def _restore_ui_state(self) -> None:
        self.case_sensitive_checkbox.setChecked(
            self.match_options["case_sensitive"]
        )
        self.whole_word_checkbox.setChecked(
            self.match_options["whole_word"]
        )
        if not self.start_check:
            self.split_match_checkbox.setChecked(self.match_options["split_match"])

    def accept(self) -> None:
        options = {
            "case_sensitive": self.case_sensitive_checkbox.isChecked(),
            "whole_word": self.whole_word_checkbox.isChecked(),
        }
        if self.start_check:
            def update_project_options(config):
                config["prompt_dictionary_match_case_sensitive"] = options["case_sensitive"]
                config["prompt_dictionary_match_whole_word"] = options["whole_word"]
            self.update_config(update_project_options)
        else:
            options["split_match"] = self.split_match_checkbox.isChecked()
        self.match_options = options
        self.check_params = options.copy()
        super().accept()
