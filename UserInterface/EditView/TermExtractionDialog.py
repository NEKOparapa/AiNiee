import os
from qfluentwidgets import (ComboBox, CheckBox, MessageBoxBase, StrongBodyLabel, 
                            InfoBar, InfoBarPosition, CaptionLabel, HyperlinkButton)
from PyQt5.QtWidgets import QGroupBox, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout
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
        self.view.setMinimumWidth(400) # 稍微加宽以容纳新布局

        # --- 顶部布局：标题和教程链接 ---
        top_layout = QHBoxLayout()
        top_layout.addWidget(StrongBodyLabel(self.tra("选择NER分词模型:")))
        top_layout.addStretch(1) # 添加伸缩，将按钮推到右侧

        tutorial_url = "https://github.com/NEKOparapa/AiNiee/wiki/NER%E6%A8%A1%E5%9E%8B%E4%B8%8B%E8%BD%BD%E6%8C%87%E5%8D%97" 
        self.tutorialButton = HyperlinkButton(url=tutorial_url, text=self.tra("模型下载"), parent=self)
        top_layout.addWidget(self.tutorialButton)
        layout.addLayout(top_layout)
        
        # --- 模型说明 ---
        model_description = self.tra("注: ja开头-日语模型，en-英语模型，ko-韩语模型")
        layout.addWidget(CaptionLabel(model_description, self))
        
        # --- 模型选择下拉框 ---
        self.model_combo = ComboBox(self)
        self.load_ner_models()
        layout.addWidget(self.model_combo)

        # --- 实体类型选择 ---
        self.entity_group = QGroupBox(self.tra("选择提取术语类型"))
        self.entity_layout = QGridLayout(self.entity_group)
        self.entity_layout.setSpacing(10)

        # 预定义模型的实体类型可选范围
        JAPANESE_TYPES = ["PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"]
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

        self.yesButton.setText(self.tra("开始提取"))
        self.cancelButton.setText(self.tra("取消"))

        # 用于存储用户选择的属性
        self.selected_model = None
        self.selected_types = []

    def load_ner_models(self):
        """
        扫描NER模型文件夹，并将模型名称加载到下拉框中
        """
        model_dir = os.path.join('.', 'Resource', 'Models', 'NER')
        if not os.path.exists(model_dir):
            self.model_combo.addItem(self.tra("未找到模型目录"))
            self.model_combo.setEnabled(False)
            self.yesButton.setEnabled(False)
            return

        models = [d.name for d in os.scandir(model_dir) if d.is_dir()]
        if models:
            self.model_combo.addItems(models)
        else:
            self.model_combo.addItem(self.tra("目录中无可用模型"))
            self.model_combo.setEnabled(False)
            self.yesButton.setEnabled(False)

    def accept(self):
        """点击“开始提取”时，收集配置数据"""
        # 从下拉框获取选定的模型名称
        self.selected_model = self.model_combo.currentText()
        
        self.selected_types = [
            text for text, cb in self.entity_checkboxes.items() if cb.isChecked()
        ]

        if not self.selected_model or not self.model_combo.isEnabled():
            InfoBar.error(
                title=self.tra('错误'),
                content=self.tra("请先选择一个可用的语言模型。"),
                duration=3000,
                position=InfoBarPosition.TOP,
                parent=self.parent()
            )
            return  # 阻止对话框关闭

        if not self.selected_types:
            InfoBar.error(
                title=self.tra('错误'),
                content=self.tra("请至少选择一个提取类型。"),
                duration=3000,
                position=InfoBarPosition.TOP,
                parent=self.parent()
            )
            return # 阻止对话框关闭
        
        super().accept()