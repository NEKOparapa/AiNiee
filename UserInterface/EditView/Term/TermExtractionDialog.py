import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QHBoxLayout
from qfluentwidgets import (ComboBox, CheckBox, MessageBoxBase, StrongBodyLabel, 
                            InfoBar, InfoBarPosition, CaptionLabel, HyperlinkButton,
                            SubtitleLabel, BodyLabel)
from Base.Base import Base

class TermExtractionDialog(Base, MessageBoxBase):
    """
    术语提取设置对话框。
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 1. 定义不同语言的标签集 ---
        self.JAPANESE_TYPES = ["PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT"]
        self.CHINESE_TYPES = self.JAPANESE_TYPES
        self.ENGLISH_TYPES = self.JAPANESE_TYPES
        self.KOREAN_TYPES = ["DT", "LC", "OG", "PS", "QT"]
        self.DEFAULT_TYPES = self.JAPANESE_TYPES

        # --- 2. 初始化主视图 ---
        self.view = QWidget(self)
        self.view.setMinimumWidth(480) # 加宽以容纳更详细的标签
        
        # 主布局
        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(20) # 增加间距，利用留白区分区块

        # =================================================
        #   UI 区域 1: 顶部标题与说明
        # =================================================
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        
        # 1.1 大标题
        title_label = SubtitleLabel(self.tra("术语提取"), self)
        header_layout.addWidget(title_label)
        
        # 1.2 功能说明
        desc_text = self.tra("选择合适的NER模型，自动识别并提取文本中的专有名词（如人名、地名）。")
        desc_label = BodyLabel(desc_text, self)
        desc_label.setTextColor(Qt.gray, Qt.gray) # 设置灰色字体作为次要信息
        desc_label.setWordWrap(True) # 允许换行
        header_layout.addWidget(desc_label)
        
        self.main_layout.addLayout(header_layout)

        # =================================================
        #   UI 区域 2: 模型选择
        # =================================================
        model_section = QVBoxLayout()
        model_section.setSpacing(8)

        # 2.1 区域标题行 (包含标题和右侧链接)
        model_header_row = QHBoxLayout()
        model_header_row.addWidget(StrongBodyLabel(self.tra("1. 选择分词模型"), self))
        model_header_row.addStretch(1)
        
        tutorial_url = "https://github.com/NEKOparapa/AiNiee/wiki/NER%E6%A8%A1%E5%9E%8B%E4%B8%8B%E8%BD%BD%E6%8C%87%E5%8D%97" 
        self.tutorialButton = HyperlinkButton(url=tutorial_url, text=self.tra("模型下载指南"), parent=self)
        model_header_row.addWidget(self.tutorialButton)
        
        model_section.addLayout(model_header_row)

        # 2.2 下拉框
        self.model_combo = ComboBox(self)
        self.load_ner_models()
        model_section.addWidget(self.model_combo)

        # 2.3 底部小提示
        prefix_tip = self.tra("提示: 日语选择ja模型，英语选择en模型，韩语选择ko模型")
        model_section.addWidget(CaptionLabel(prefix_tip, self))
        
        self.main_layout.addLayout(model_section)

        # =================================================
        #   UI 区域 3: 实体类型选择 (替代原来的 GroupBox)
        # =================================================
        entity_section = QVBoxLayout()
        entity_section.setSpacing(10)

        # 3.1 区域标题
        entity_section.addWidget(StrongBodyLabel(self.tra("2. 提取内容类型"), self))

        # 3.2 复选框容器 (使用 QWidget + Grid 替代 GroupBox)
        self.entity_container = QWidget(self)
        self.entity_layout = QGridLayout(self.entity_container)
        self.entity_layout.setContentsMargins(0, 5, 0, 5) # 稍微缩进一点
        self.entity_layout.setVerticalSpacing(12)
        self.entity_layout.setHorizontalSpacing(20)
        
        self.entity_checkboxes = {}
        
        entity_section.addWidget(self.entity_container)
        self.main_layout.addLayout(entity_section)

        # =================================================

        # --- 信号连接 ---
        self.model_combo.currentTextChanged.connect(self._update_entity_checkboxes)

        # --- 初始加载 ---
        if self.model_combo.count() > 0:
            self._update_entity_checkboxes(self.model_combo.currentText())

        # 添加视图到 MessageBox
        self.viewLayout.addWidget(self.view)

        # 按钮文字
        self.yesButton.setText(self.tra("开始提取"))
        self.cancelButton.setText(self.tra("取消"))

        self.selected_model = None
        self.selected_types = []

    def _clear_layout(self, layout):
        if layout is None: return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _update_entity_checkboxes(self, model_name: str):
        """
        根据模型名称更新实体类型复选框
        """
        # 1. 确定标签列表
        if model_name.startswith(('ja_', 'ja-')):
            types_to_display = self.JAPANESE_TYPES
        elif model_name.startswith(('en_', 'en-')):
            types_to_display = self.ENGLISH_TYPES
        elif model_name.startswith(('zh_', 'zh-')):
            types_to_display = self.CHINESE_TYPES
        elif model_name.startswith(('ko_', 'ko-')):
            types_to_display = self.KOREAN_TYPES
        else:
            types_to_display = self.DEFAULT_TYPES

        # 2. 清空旧布局
        self._clear_layout(self.entity_layout)
        self.entity_checkboxes.clear()

        # 3. 标签翻译映射
        type_map = {
            "PERSON": self.tra("人物 (Person)"),
            "ORG": self.tra("组织 (Org)"),
            "GPE": self.tra("国家/城市 (GPE)"),
            "LOC": self.tra("地点 (Loc)"),
            "PRODUCT": self.tra("产品/作品 (Product)"),
            "EVENT": self.tra("事件 (Event)"),
            # 韩语标签映射
            "DT": self.tra("日期 (Date)"),
            "LC": self.tra("地点 (Location)"),
            "OG": self.tra("组织 (Org)"),
            "PS": self.tra("人物 (Person)"),
            "QT": self.tra("数量 (Quantity)")
        }

        # 4. 创建新的复选框
        row, col = 0, 0
        for entity_type in types_to_display:
            # 获取友好的显示文本
            display_text = type_map.get(entity_type, entity_type)
            
            checkbox = CheckBox(display_text, self)
            checkbox.setChecked(True)
            
            # 存储引用
            self.entity_checkboxes[entity_type] = checkbox
            
            self.entity_layout.addWidget(checkbox, row, col)
            
            # 每行显示 2 个，布局更宽松清晰
            col += 1
            if col > 1: 
                col = 0
                row += 1

    def load_ner_models(self):
        """扫描NER模型"""
        model_dir = os.path.join('.', 'Resource', 'Models', 'ner')
        if not os.path.exists(model_dir):
            self.model_combo.addItem(self.tra("未找到模型目录"))
            self.model_combo.setEnabled(False)
            self.yesButton.setEnabled(False)
            return

        models = []
        try:
            models = [d.name for d in os.scandir(model_dir) if d.is_dir()]
        except:
            pass

        if models:
            self.model_combo.addItems(sorted(models))
        else:
            self.model_combo.addItem(self.tra("目录中无可用模型"))
            self.model_combo.setEnabled(False)
            self.yesButton.setEnabled(False)

    def accept(self):
        """数据收集与校验"""
        self.selected_model = self.model_combo.currentText()
        
        self.selected_types = [
            k for k, cb in self.entity_checkboxes.items() if cb.isChecked()
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