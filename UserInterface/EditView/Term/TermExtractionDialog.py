import os
from qfluentwidgets import (ComboBox, CheckBox, MessageBoxBase, StrongBodyLabel, 
                            InfoBar, InfoBarPosition, CaptionLabel, HyperlinkButton)
from PyQt5.QtWidgets import QGroupBox, QWidget, QVBoxLayout, QGridLayout, QHBoxLayout
from Base.Base import Base

class TermExtractionDialog(Base, MessageBoxBase):
    """
    术语提取设置对话框。
    (改进版：根据模型名称动态显示实体类型)
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 1. 定义不同语言的标签集 ---
        self.JAPANESE_TYPES = ["PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"]
        self.CHINESE_TYPES = self.JAPANESE_TYPES  # 中文模型使用与日语相同的标签集
        self.ENGLISH_TYPES = self.JAPANESE_TYPES  # 英文模型使用与日语相同的标签集
        self.KOREAN_TYPES = ["DT", "LC", "OG", "PS", "QT"]
        self.DEFAULT_TYPES = self.JAPANESE_TYPES # 如果没有匹配的前缀，使用默认列表

        self.view = QWidget(self)
        layout = QVBoxLayout(self.view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)
        self.view.setMinimumWidth(400)

        # --- 顶部布局：标题和教程链接 ---
        top_layout = QHBoxLayout()
        top_layout.addWidget(StrongBodyLabel(self.tra("选择NER分词模型:")))
        top_layout.addStretch(1)
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
        self.entity_checkboxes = {} # 用于存储复选框的字典
        layout.addWidget(self.entity_group)

        # --- 2. 连接信号，当模型选择变化时更新复选框 ---
        self.model_combo.currentTextChanged.connect(self._update_entity_checkboxes)

        # --- 3. 初始加载时，根据默认选中的模型更新一次复选框 ---
        if self.model_combo.count() > 0:
            self._update_entity_checkboxes(self.model_combo.currentText())

        # 将自定义视图添加到对话框
        self.viewLayout.addWidget(self.view)

        self.yesButton.setText(self.tra("开始提取"))
        self.cancelButton.setText(self.tra("取消"))

        self.selected_model = None
        self.selected_types = []

    def _clear_layout(self, layout):
        """辅助函数，用于清空布局中的所有小部件"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _update_entity_checkboxes(self, model_name: str):
        """
        核心函数：根据模型名称更新实体类型复选框
        """
        # 根据模型名称前缀选择标签列表
        if model_name.startswith(('ja_', 'ja-')):
            types_to_display = self.JAPANESE_TYPES
        elif model_name.startswith(('en_', 'en-')):
            types_to_display = self.ENGLISH_TYPES
        elif model_name.startswith(('zh_', 'zh-')):
            types_to_display = self.CHINESE_TYPES
        elif model_name.startswith(('ko_', 'ko-')):
            types_to_display = self.KOREAN_TYPES
        else:
            types_to_display = self.DEFAULT_TYPES # 提供默认选项

        # 清空旧的复选框
        self._clear_layout(self.entity_layout)
        self.entity_checkboxes.clear()

        # 创建并添加新的复选框
        row, col = 0, 0
        for entity_type in types_to_display:
            checkbox = CheckBox(entity_type, self)
            checkbox.setChecked(True)
            self.entity_checkboxes[entity_type] = checkbox
            self.entity_layout.addWidget(checkbox, row, col)
            col += 1
            if col > 2:  # 每行最多3个
                col = 0
                row += 1

    def load_ner_models(self):
        """
        扫描NER模型文件夹，并将模型名称加载到下拉框中
        """
        model_dir = os.path.join('.', 'Resource', 'Models', 'ner')
        if not os.path.exists(model_dir):
            self.model_combo.addItem(self.tra("未找到模型目录"))
            self.model_combo.setEnabled(False)
            self.yesButton.setEnabled(False)
            return

        models = [d.name for d in os.scandir(model_dir) if d.is_dir()]
        if models:
            self.model_combo.addItems(sorted(models)) # 对模型排序，更美观
        else:
            self.model_combo.addItem(self.tra("目录中无可用模型"))
            self.model_combo.setEnabled(False)
            self.yesButton.setEnabled(False)

    def accept(self):
        """点击“开始提取”时，收集配置数据"""
        self.selected_model = self.model_combo.currentText()
        
        self.selected_types = [
            text for text, cb in self.entity_checkboxes.items() if cb.isChecked()
        ]

        if not self.selected_model or not self.model_combo.isEnabled() or "未找到" in self.selected_model or "无可用" in self.selected_model:
            InfoBar.error(
                title=self.tra('错误'),
                content=self.tra("请先选择一个可用的语言模型。"),
                duration=3000,
                position=InfoBarPosition.TOP,
                parent=self.parent()
            )
            return

        if not self.selected_types:
            InfoBar.error(
                title=self.tra('错误'),
                content=self.tra("请至少选择一个提取类型。"),
                duration=3000,
                position=InfoBarPosition.TOP,
                parent=self.parent()
            )
            return
        
        super().accept()