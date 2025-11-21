from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QHBoxLayout
from qfluentwidgets import CheckBox, ComboBox, MessageBoxBase, StrongBodyLabel, CaptionLabel
from Base.Base import Base

class LanguageCheckDialog(Base, MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 1. 定义默认配置
        self.default = {
            "check_target_polish": False, # False 表示检测译文，True 表示检测润文
            "check_lang_mode_text": "judge", # "report" 或 "judge",juedge 为精准判断
            "rule_check_exclusion": True,
            "rule_check_terminology": False,
            "rule_check_auto_process": True,
            "rule_check_placeholder": True,
            "rule_check_number": True,
            "rule_check_example": True,
            "rule_check_newline": True
        }
        
        self.config_data = self.save_config(self.load_config_from_default())

        self.view = QWidget(self)
        self.view_layout = QVBoxLayout(self.view)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.setSpacing(20)
        self.view.setMinimumWidth(600) 

        self._init_ui()
        self._restore_ui_state()
        self._connect_signals()

        self.viewLayout.addWidget(self.view)
        
        self.yesButton.setText(self.tra("开始检查"))
        self.cancelButton.setText(self.tra("取消"))

    def _init_ui(self):
        # ... (保持原有 settings_container 代码不变) ...
        self.settings_container = QWidget()
        self.settings_layout = QGridLayout(self.settings_container)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_layout.setVerticalSpacing(15)
        self.settings_layout.setHorizontalSpacing(15)

        self.target_label = StrongBodyLabel(self.tra("检测对象:"), self)
        self.target_combo = ComboBox(self)
        self.target_combo.addItems([self.tra("译文"), self.tra("润文")])
        
        self.mode_label = StrongBodyLabel(self.tra("语言检测:"), self)
        self.mode_combo = ComboBox(self)
        self.mode_combo.addItems([self.tra("宏观统计"), self.tra("精准判断")])

        self.settings_layout.addWidget(self.target_label, 0, 0)
        self.settings_layout.addWidget(self.target_combo, 0, 1)
        self.settings_layout.addWidget(self.mode_label, 1, 0)
        self.settings_layout.addWidget(self.mode_combo, 1, 1)

        self.view_layout.addWidget(self.settings_container)

        # ================= 规则检查项 =================
        self.view_layout.addWidget(StrongBodyLabel(self.tra("规则检查项"), self))
        
        # [新增] 术语表检查 CheckBox
        self.check_terminology = CheckBox(self.tra("术语表检查"), self)
        self.check_exclusion = CheckBox(self.tra("禁翻表检查"), self)
        self.check_auto_process = CheckBox(self.tra("自动处理检查"), self)
        self.check_placeholder = CheckBox(self.tra("占位符残留"), self)
        self.check_number = CheckBox(self.tra("数字序号残留"), self)
        self.check_example = CheckBox(self.tra("示例文本复读"), self)
        self.check_newline = CheckBox(self.tra("换行符一致性"), self)

        # [新增] 添加选项说明
        self._add_option(self.check_terminology, self.tra("检查译文中是否包含术语表中的预定义译法"))
        self._add_option(self.check_exclusion, self.tra("检查译文中是否正确保留禁翻内容"))
        self._add_option(self.check_auto_process, self.tra("检查默认处理规则是否被正确执行"))
        self._add_option(self.check_placeholder, self.tra("检查 [P0] 等占位标签是否残留在文本中"))
        self._add_option(self.check_number, self.tra("检查行首数字编号 (1.) 是否残留"))
        self._add_option(self.check_example, self.tra("检查是否存在由模型生成的无效内容"))
        self._add_option(self.check_newline, self.tra("检查译文换行符数量是否与原文一致"))

    def _add_option(self, checkbox: CheckBox, description: str):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        layout.addWidget(checkbox)
        desc_label = CaptionLabel(description, self)
        desc_label.setTextColor(QColor(120, 120, 120), QColor(160, 160, 160))
        layout.addWidget(desc_label, 1)
        self.view_layout.addWidget(container)
        self.view_layout.addSpacing(5)

    def _restore_ui_state(self):
        config = self.config_data
        
        is_polish = config.get("check_target_polish", False)
        self.target_combo.setCurrentIndex(1 if is_polish else 0)
        
        mode_code = config.get("check_lang_mode_text", "report")
        if mode_code == "judge":
            self.mode_combo.setCurrentText(self.tra("精准判断"))
        else:
            self.mode_combo.setCurrentText(self.tra("宏观统计"))

        # [新增] 恢复术语表状态
        self.check_terminology.setChecked(config.get("rule_check_terminology", True))
        self.check_exclusion.setChecked(config.get("rule_check_exclusion", True))
        self.check_auto_process.setChecked(config.get("rule_check_auto_process", True))
        self.check_placeholder.setChecked(config.get("rule_check_placeholder", True))
        self.check_number.setChecked(config.get("rule_check_number", True))
        self.check_example.setChecked(config.get("rule_check_example", True))
        self.check_newline.setChecked(config.get("rule_check_newline", True))

    def _connect_signals(self):
        self.target_combo.currentIndexChanged.connect(self._on_setting_changed)
        self.mode_combo.currentTextChanged.connect(self._on_setting_changed)
        
        # [新增] 连接信号
        self.check_terminology.stateChanged.connect(self._on_setting_changed)
        self.check_exclusion.stateChanged.connect(self._on_setting_changed)
        self.check_auto_process.stateChanged.connect(self._on_setting_changed)
        self.check_placeholder.stateChanged.connect(self._on_setting_changed)
        self.check_number.stateChanged.connect(self._on_setting_changed)
        self.check_example.stateChanged.connect(self._on_setting_changed)
        self.check_newline.stateChanged.connect(self._on_setting_changed)

    def _on_setting_changed(self):
        config = self.load_config()
        
        config["check_target_polish"] = (self.target_combo.currentIndex() == 1)
        
        if self.mode_combo.currentText() == self.tra("精准判断"):
            config["check_lang_mode_text"] = "judge"
        else:
            config["check_lang_mode_text"] = "report"
        
        # [新增] 保存术语表状态
        config["rule_check_terminology"] = self.check_terminology.isChecked()
        config["rule_check_exclusion"] = self.check_exclusion.isChecked()
        config["rule_check_auto_process"] = self.check_auto_process.isChecked()
        config["rule_check_placeholder"] = self.check_placeholder.isChecked()
        config["rule_check_number"] = self.check_number.isChecked()
        config["rule_check_example"] = self.check_example.isChecked()
        config["rule_check_newline"] = self.check_newline.isChecked()
        
        self.save_config(config)
        self.config_data = config

    def accept(self):
        is_polish = self.config_data.get("check_target_polish", False)
        mode_code = self.config_data.get("check_lang_mode_text", "report")

        self.check_params = {
            "target": "polish" if is_polish else "translate",
            "mode": mode_code,
            "rules": {
                "terminology": self.check_terminology.isChecked(),
                "exclusion": self.check_exclusion.isChecked(),
                "auto_process": self.check_auto_process.isChecked(),
                "placeholder": self.check_placeholder.isChecked(),
                "number": self.check_number.isChecked(),
                "example": self.check_example.isChecked(),
                "newline": self.check_newline.isChecked()
            }
        }
        super().accept()