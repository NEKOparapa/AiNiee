from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGridLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ComboBox, DoubleSpinBox, MessageBoxBase, SpinBox, StrongBodyLabel

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin


class LanguageCheckDialog(ConfigMixin, Base, MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.default = {
            "check_lang_mode_text": "judge",
            "check_chunk_size": 20,
            "check_threshold_ratio": 0.75,
        }
        self.config_data = self.save_config(self.load_config_from_default())

        self.view = QWidget(self)
        self.view_layout = QVBoxLayout(self.view)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.setSpacing(20)
        self.view.setMinimumWidth(520)

        self._init_ui()
        self._restore_ui_state()
        self._connect_signals()

        self.viewLayout.addWidget(self.view)
        self.yesButton.setText(self.tra("开始检查"))
        self.cancelButton.setText(self.tra("取消"))

    def _init_ui(self):
        settings_container = QWidget(self)
        settings_layout = QGridLayout(settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setVerticalSpacing(16)
        settings_layout.setHorizontalSpacing(16)

        self.mode_label = StrongBodyLabel(self.tra("语言检测"), self)
        self.mode_combo = ComboBox(self)
        self.mode_combo.addItems([self.tra("宏观统计"), self.tra("精准判断")])

        self.chunk_label = StrongBodyLabel(self.tra("检测分块行数"), self)
        self.chunk_spin = SpinBox(self)
        self.chunk_spin.setRange(1, 999)
        self.chunk_spin.setFixedWidth(160)

        self.threshold_label = StrongBodyLabel(self.tra("检测阈值"), self)
        self.threshold_spin = DoubleSpinBox(self)
        self.threshold_spin.setRange(0.10, 1.00)
        self.threshold_spin.setSingleStep(0.01)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setFixedWidth(160)

        settings_layout.addWidget(self.mode_label, 0, 0)
        settings_layout.addWidget(self.mode_combo, 0, 1)
        settings_layout.addWidget(self.chunk_label, 1, 0)
        settings_layout.addWidget(self.chunk_spin, 1, 1)
        settings_layout.addWidget(self.threshold_label, 2, 0)
        settings_layout.addWidget(self.threshold_spin, 2, 1)

        self.view_layout.addWidget(settings_container)

        note_label = CaptionLabel(self.tra("检测分块行数与检测阈值只在精准判断中生效"), self)
        note_label.setTextColor(QColor(120, 120, 120), QColor(160, 160, 160))
        note_label.setAlignment(Qt.AlignCenter)
        note_label.setWordWrap(True)
        self.view_layout.addWidget(note_label)

    def _restore_ui_state(self):
        mode_code = self.config_data.get("check_lang_mode_text", "judge")
        self.mode_combo.setCurrentText(self.tra("精准判断") if mode_code == "judge" else self.tra("宏观统计"))
        self.chunk_spin.setValue(max(1, int(self.config_data.get("check_chunk_size", 20))))
        self.threshold_spin.setValue(float(self.config_data.get("check_threshold_ratio", 0.75)))

    def _connect_signals(self):
        self.mode_combo.currentTextChanged.connect(self._on_setting_changed)
        self.chunk_spin.valueChanged.connect(self._on_setting_changed)
        self.threshold_spin.valueChanged.connect(self._on_setting_changed)

    def _on_setting_changed(self):
        config = self.load_config()
        config["check_lang_mode_text"] = "judge" if self.mode_combo.currentText() == self.tra("精准判断") else "report"
        config["check_chunk_size"] = self.chunk_spin.value()
        config["check_threshold_ratio"] = self.threshold_spin.value()
        self.save_config(config)
        self.config_data = config

    def accept(self):
        self.check_params = {
            "mode": self.config_data.get("check_lang_mode_text", "judge"),
            "chunk_size": self.chunk_spin.value(),
            "threshold": self.threshold_spin.value(),
        }
        super().accept()
