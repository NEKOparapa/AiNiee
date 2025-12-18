from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QHBoxLayout
from qfluentwidgets import CheckBox, ComboBox, MessageBoxBase, StrongBodyLabel, CaptionLabel, SpinBox, DoubleSpinBox
from ModuleFolders.Base.Base import Base

class LanguageCheckDialog(Base, MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. 定义默认配置
        self.default = {
            "check_target_polish": False, # False 表示检测译文，True 表示检测润文
            "check_lang_mode_text": "judge", # "report" 或 "judge", judge 为精准判断
            "check_chunk_size": 20,          #  检测分块行数
            "check_threshold_ratio": 0.75,   #  检测阈值占比
            "rule_check_exclusion": True,
            "rule_check_terminology": False,
            "rule_check_auto_process": True,
            "rule_check_placeholder": True,
            "rule_check_number": True,
            "rule_check_example": True,
            "rule_check_newline": True,
            "rule_check_untranslated": True
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

        self.settings_container = QWidget()
        self.settings_layout = QGridLayout(self.settings_container)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_layout.setVerticalSpacing(15)
        self.settings_layout.setHorizontalSpacing(15)

        # 检测对象
        self.target_label = StrongBodyLabel(self.tra("检测对象:"), self)
        self.target_combo = ComboBox(self)
        self.target_combo.addItems([self.tra("译文"), self.tra("润文")])

        # 语言检测模式
        self.mode_label = StrongBodyLabel(self.tra("语言检测:"), self)
        self.mode_combo = ComboBox(self)
        self.mode_combo.addItems([self.tra("宏观统计"), self.tra("精准判断")])

        # 检测分块行数
        self.chunk_label = StrongBodyLabel(self.tra("检测分块行数:"), self)
        self.chunk_spin = SpinBox(self)
        self.chunk_spin.setRange(1, 99)
        self.chunk_spin.setFixedWidth(140)

        # 检测阈值占比
        self.threshold_label = StrongBodyLabel(self.tra("检测阈值:"), self)
        self.threshold_spin = DoubleSpinBox(self)
        self.threshold_spin.setRange(0.10, 1.00)
        self.threshold_spin.setSingleStep(0.01)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setFixedWidth(140)

        # 布局添加
        self.settings_layout.addWidget(self.target_label, 0, 0)
        self.settings_layout.addWidget(self.target_combo, 0, 1)
        self.settings_layout.addWidget(self.mode_label, 1, 0)
        self.settings_layout.addWidget(self.mode_combo, 1, 1)
        self.settings_layout.addWidget(self.chunk_label, 2, 0)
        self.settings_layout.addWidget(self.chunk_spin, 2, 1)
        self.settings_layout.addWidget(self.threshold_label, 3, 0)
        self.settings_layout.addWidget(self.threshold_spin, 3, 1)

        self.view_layout.addWidget(self.settings_container)

        # 说明文字
        self.note_label = CaptionLabel(self.tra("检测分块行数与检测阈值只在精准判断中生效"), self)
        self.note_label.setTextColor(QColor(120, 120, 120), QColor(160, 160, 160))
        self.note_label.setAlignment(Qt.AlignCenter)
        self.view_layout.addWidget(self.note_label)

        # ================= 规则检查项 =================
        self.view_layout.addWidget(StrongBodyLabel(self.tra("规则检查项"), self))

        # 1. 初始化 CheckBox 对象
        self.check_untranslated = CheckBox(self.tra("未翻译检查"), self)
        self.check_terminology = CheckBox(self.tra("术语表检查"), self)
        self.check_exclusion = CheckBox(self.tra("禁翻表检查"), self)
        self.check_auto_process = CheckBox(self.tra("自动处理检查"), self)
        self.check_placeholder = CheckBox(self.tra("占位符残留"), self)
        self.check_number = CheckBox(self.tra("数字序号残留"), self)
        self.check_example = CheckBox(self.tra("示例文本复读"), self)
        self.check_newline = CheckBox(self.tra("换行符一致性"), self)

        # 2. 定义检查项列表 (组件, 说明文字)
        rule_items = [
            (self.check_untranslated, self.tra("检查翻译状态为待翻译或译文为空的条目")),
            (self.check_terminology, self.tra("检查译文中是否包含术语表中的预定义译法")),
            (self.check_exclusion, self.tra("检查译文中是否正确保留禁翻内容")),
            (self.check_auto_process, self.tra("检查默认处理规则是否被正确执行")),
            (self.check_placeholder, self.tra("检查 [P0] 等占位标签是否残留在文本中")),
            (self.check_number, self.tra("检查行首数字编号 (1.) 是否残留")),
            (self.check_example, self.tra("检查是否存在由模型生成的无效内容")),
            (self.check_newline, self.tra("检查译文换行符数量是否与原文一致"))
        ]

        # 3. 创建网格容器
        self.rules_container = QWidget()
        self.rules_grid = QGridLayout(self.rules_container)
        self.rules_grid.setContentsMargins(0, 0, 0, 0)
        self.rules_grid.setHorizontalSpacing(20) # 列间距
        self.rules_grid.setVerticalSpacing(16)   # 行间距

        # 4. 循环添加到网格
        for i, (checkbox, description) in enumerate(rule_items):
            row = i // 2
            col = i % 2
            item_widget = self._create_rule_item(checkbox, description)
            self.rules_grid.addWidget(item_widget, row, col)

        self.view_layout.addWidget(self.rules_container)

    def _create_rule_item(self, checkbox: CheckBox, description: str) -> QWidget:
        """创建一个包含复选框和下方缩进说明文字的 Widget"""
        container = QWidget()
        # 使用垂直布局：上面是复选框，下面是说明
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 添加复选框
        layout.addWidget(checkbox)
        
        # 添加说明文字
        desc_label = CaptionLabel(description, self)
        desc_label.setTextColor(QColor(120, 120, 120), QColor(160, 160, 160))
        desc_label.setWordWrap(True) # 允许自动换行
        
        # 给说明文字做一个容器来设置缩进 (对齐复选框文字)
        desc_container = QWidget()
        desc_layout = QHBoxLayout(desc_container)
        desc_layout.setContentsMargins(28, 0, 0, 0) # 左侧缩进约28px，避开复选框图标
        desc_layout.setSpacing(0)
        desc_layout.addWidget(desc_label)
        
        layout.addWidget(desc_container)
        
        return container

    def _restore_ui_state(self):
        config = self.config_data

        is_polish = config.get("check_target_polish", False)
        self.target_combo.setCurrentIndex(1 if is_polish else 0)

        mode_code = config.get("check_lang_mode_text", "report")
        if mode_code == "judge":
            self.mode_combo.setCurrentText(self.tra("精准判断"))
        else:
            self.mode_combo.setCurrentText(self.tra("宏观统计"))

        #  恢复数值，若配置为0或不存在则使用默认值
        chunk_val = config.get("check_chunk_size", 20)
        self.chunk_spin.setValue(chunk_val if chunk_val > 0 else 20)

        thresh_val = config.get("check_threshold_ratio", 0.75)
        self.threshold_spin.setValue(thresh_val if thresh_val > 0 else 0.75)

        # 恢复复选框状态
        self.check_untranslated.setChecked(config.get("rule_check_untranslated", True))
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

        #  连接数值变化信号
        self.chunk_spin.valueChanged.connect(self._on_setting_changed)
        self.threshold_spin.valueChanged.connect(self._on_setting_changed)

        # 连接信号
        self.check_untranslated.stateChanged.connect(self._on_setting_changed)
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

        #  保存数值
        config["check_chunk_size"] = self.chunk_spin.value()
        config["check_threshold_ratio"] = self.threshold_spin.value()

        # 保存复选框状态
        config["rule_check_untranslated"] = self.check_untranslated.isChecked()
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
            #  传递参数
            "chunk_size": self.chunk_spin.value(),
            "threshold": self.threshold_spin.value(),
            "rules": {
                "untranslated": self.check_untranslated.isChecked(),
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