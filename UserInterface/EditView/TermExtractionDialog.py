from qfluentwidgets import ComboBox, CheckBox, MessageBoxBase, StrongBodyLabel
from PyQt5.QtWidgets import QGroupBox, QWidget, QVBoxLayout, QGridLayout
from Base.Base import Base

class TermExtractionDialog(Base, MessageBoxBase):
    """
    术语提取设置对话框。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QWidget(self)
        layout = QVBoxLayout(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        self.view.setMinimumWidth(350)

        # 1. 语言模型选择
        layout.addWidget(StrongBodyLabel(self.tr("选择模型语言:")))
        self.language_combo = ComboBox(self)
        # 示例模型，实际应用中可以动态加载
        self.language_combo.addItems(["Japanese (ja_core_news_sm)"]) 
        layout.addWidget(self.language_combo)

        # 2. 实体类型选择
        self.entity_group = QGroupBox(self.tr("选择提取类型"))
        self.entity_layout = QGridLayout(self.entity_group)
        self.entity_layout.setSpacing(10)
        
        # 预定义日语模型的实体类型
        # 可通过 spaCy 模型文档或检查模型本身获得
        JAPANESE_TYPES = ["PERSON", "ORG", "GPE", "LOC", "DATE", "PRODUCT", "EVENT", "NORP"]
        self.entity_checkboxes = {}

        row, col = 0, 0
        for entity_type in JAPANESE_TYPES:
            checkbox = CheckBox(entity_type, self)
            checkbox.setChecked(True)  # 默认全部选中
            self.entity_checkboxes[entity_type] = checkbox
            self.entity_layout.addWidget(checkbox, row, col)
            col += 1
            if col > 2:  # 每行最多3个
                col = 0
                row += 1
        
        layout.addWidget(self.entity_group)

        # 将自定义视图添加到对话框
        self.viewLayout.addWidget(self.view)

        self.yesButton.setText(self.tr("开始提取"))
        self.cancelButton.setText(self.tr("取消"))

        # 用于存储用户选择的属性
        self.language = "Japanese"
        self.selected_types = []

    def accept(self):
        """点击“开始提取”时，收集配置数据"""

        self.language = "Japanese" # 目前只支持日语
        
        self.selected_types = [
            text for text, cb in self.entity_checkboxes.items() if cb.isChecked()
        ]

        if not self.selected_types:
            self.error("请至少选择一项类型")
            pass 
        
        super().accept()