from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, CheckBox, MessageBoxBase, StrongBodyLabel

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin


class RuleCheckDialog(ConfigMixin, Base, MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.default = {
            "rule_check_exclusion": True,
            "rule_check_auto_process": True,
            "rule_check_placeholder": True,
            "rule_check_number": True,
            "rule_check_example": True,
            "rule_check_newline": True,
            "rule_check_untranslated": True,
        }
        self.config_data = self.save_config(self.load_config_from_default())

        self.view = QWidget(self)
        self.view_layout = QVBoxLayout(self.view)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.setSpacing(20)
        self.view.setMinimumWidth(650)

        self._init_ui()
        self._restore_ui_state()
        self._connect_signals()

        self.viewLayout.addWidget(self.view)
        self.yesButton.setText(self.tra("开始检查"))
        self.cancelButton.setText(self.tra("取消"))

    def _init_ui(self):
        self.view_layout.addWidget(StrongBodyLabel(self.tra("规则检查项"), self))

        self.check_untranslated = CheckBox(self.tra("未翻译检查"), self)
        self.check_exclusion = CheckBox(self.tra("禁翻表检查"), self)
        self.check_auto_process = CheckBox(self.tra("自动处理检查"), self)
        self.check_placeholder = CheckBox(self.tra("占位符残留"), self)
        self.check_number = CheckBox(self.tra("数字序号残留"), self)
        self.check_example = CheckBox(self.tra("示例文本复读"), self)
        self.check_newline = CheckBox(self.tra("换行符一致性"), self)

        rule_items = [
            (self.check_untranslated, self.tra("检查翻译状态为未翻译或译文为空的条目")),
            (self.check_exclusion, self.tra("检查译文中是否正确保留禁翻内容")),
            (self.check_auto_process, self.tra("检查默认处理规则是否被正确执行")),
            (self.check_placeholder, self.tra("检查 [P0] 等占位标签是否残留在文本中")),
            (self.check_number, self.tra("检查行首数字编号 (1.) 是否残留")),
            (self.check_example, self.tra("检查是否存在由模型生成的无效内容")),
            (self.check_newline, self.tra("检查译文换行符数量是否与原文一致")),
        ]

        rules_container = QWidget(self)
        rules_grid = QGridLayout(rules_container)
        rules_grid.setContentsMargins(0, 0, 0, 0)
        rules_grid.setHorizontalSpacing(20)
        rules_grid.setVerticalSpacing(16)

        for index, (checkbox, description) in enumerate(rule_items):
            rules_grid.addWidget(self._create_rule_item(checkbox, description), index // 2, index % 2)

        self.view_layout.addWidget(rules_container)

    def _create_rule_item(self, checkbox: CheckBox, description: str) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(checkbox)

        desc_label = CaptionLabel(description, self)
        desc_label.setTextColor(QColor(120, 120, 120), QColor(160, 160, 160))
        desc_label.setWordWrap(True)

        desc_container = QWidget(self)
        desc_layout = QHBoxLayout(desc_container)
        desc_layout.setContentsMargins(28, 0, 0, 0)
        desc_layout.setSpacing(0)
        desc_layout.addWidget(desc_label)

        layout.addWidget(desc_container)
        return container

    def _restore_ui_state(self):
        config = self.config_data
        self.check_untranslated.setChecked(config.get("rule_check_untranslated", True))
        self.check_exclusion.setChecked(config.get("rule_check_exclusion", True))
        self.check_auto_process.setChecked(config.get("rule_check_auto_process", True))
        self.check_placeholder.setChecked(config.get("rule_check_placeholder", True))
        self.check_number.setChecked(config.get("rule_check_number", True))
        self.check_example.setChecked(config.get("rule_check_example", True))
        self.check_newline.setChecked(config.get("rule_check_newline", True))

    def _connect_signals(self):
        self.check_untranslated.stateChanged.connect(self._on_setting_changed)
        self.check_exclusion.stateChanged.connect(self._on_setting_changed)
        self.check_auto_process.stateChanged.connect(self._on_setting_changed)
        self.check_placeholder.stateChanged.connect(self._on_setting_changed)
        self.check_number.stateChanged.connect(self._on_setting_changed)
        self.check_example.stateChanged.connect(self._on_setting_changed)
        self.check_newline.stateChanged.connect(self._on_setting_changed)

    def _on_setting_changed(self):
        config = self.load_config()
        config["rule_check_untranslated"] = self.check_untranslated.isChecked()
        config["rule_check_exclusion"] = self.check_exclusion.isChecked()
        config["rule_check_auto_process"] = self.check_auto_process.isChecked()
        config["rule_check_placeholder"] = self.check_placeholder.isChecked()
        config["rule_check_number"] = self.check_number.isChecked()
        config["rule_check_example"] = self.check_example.isChecked()
        config["rule_check_newline"] = self.check_newline.isChecked()
        self.save_config(config)
        self.config_data = config

    def accept(self):
        self.check_params = {
            "rules": {
                "untranslated": self.check_untranslated.isChecked(),
                "exclusion": self.check_exclusion.isChecked(),
                "auto_process": self.check_auto_process.isChecked(),
                "placeholder": self.check_placeholder.isChecked(),
                "number": self.check_number.isChecked(),
                "example": self.check_example.isChecked(),
                "newline": self.check_newline.isChecked(),
            }
        }
        super().accept()
