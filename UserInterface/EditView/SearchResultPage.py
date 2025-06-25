import os
import re 
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem, 
                             QAbstractItemView, QHeaderView, QHBoxLayout, QSpacerItem, QSizePolicy)

from qfluentwidgets import (TableWidget, PushButton, PrimaryPushButton, LineEdit, StrongBodyLabel,
                            CheckBox, FluentIcon)
from Base.Base import Base


class SearchResultPage(Base, QWidget):
    # 定义列索引常量
    COL_FILE = 0
    COL_ROW = 1
    COL_SOURCE = 2
    COL_TRANS = 3
    COL_POLISH = 4

    def __init__(self, search_results: list, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName('SearchResultPage')
        
        self.cache_manager = cache_manager
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8) # 调整边距以容纳新控件
        self.layout.setSpacing(10) # 增加控件间距

        # 初始化顶部工具栏
        #self._init_toolbar()
        
        # 初始化批量替换面板
        self._init_replace_panel()

        # 初始化表格
        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)
        
        self._populate_data(search_results)

        self.table.itemChanged.connect(self._on_item_changed)

    def _init_toolbar(self):
        """初始化顶部工具栏"""
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加一个弹簧，将按钮推到右侧
        toolbar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.replace_button = PushButton(FluentIcon.EDIT, self.tra("批量替换"), self)
        self.replace_button.clicked.connect(self._toggle_replace_panel)
        toolbar_layout.addWidget(self.replace_button)

        self.layout.addLayout(toolbar_layout)

    def _init_replace_panel(self):
        """初始化批量替换面板"""
        self.replace_panel = QWidget(self)
        self.replace_panel.setObjectName("replacePanel")
        
        panel_layout = QVBoxLayout(self.replace_panel)
        panel_layout.setContentsMargins(0, 0, 0, 5)
        panel_layout.setSpacing(8)

        # 创建两行布局
        row1_layout = QHBoxLayout()
        row2_layout = QHBoxLayout()

        # --- 第一行：查找和替换输入框 ---
        row1_layout.addWidget(StrongBodyLabel(self.tra("查找内容:"), self))
        self.find_input = LineEdit(self)
        self.find_input.setPlaceholderText(self.tra("输入要查找的文本..."))
        row1_layout.addWidget(self.find_input)
        
        row1_layout.addSpacing(20)

        row1_layout.addWidget(StrongBodyLabel(self.tra("替换为:"), self))
        self.replace_input = LineEdit(self)
        self.replace_input.setPlaceholderText(self.tra("输入替换后的文本..."))
        row1_layout.addWidget(self.replace_input)
        
        # --- 第二行：选项和操作按钮 ---
        row2_layout.addWidget(StrongBodyLabel(self.tra("选项:"), self))
        self.case_checkbox = CheckBox(self.tra("区分大小写"), self)
        self.whole_word_checkbox = CheckBox(self.tra("全词匹配"), self)
        row2_layout.addWidget(self.case_checkbox)
        row2_layout.addWidget(self.whole_word_checkbox)
        
        row2_layout.addSpacing(15)
        
        row2_layout.addWidget(StrongBodyLabel(self.tra("范围:"), self))
        self.trans_col_checkbox = CheckBox(self.tra("译文列"), self)
        self.polish_col_checkbox = CheckBox(self.tra("润文列"), self)
        self.trans_col_checkbox.setChecked(True) # 默认选中译文列
        row2_layout.addWidget(self.trans_col_checkbox)
        row2_layout.addWidget(self.polish_col_checkbox)

        row2_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        self.replace_all_button = PrimaryPushButton(self.tra("全部替换"), self)
        self.replace_all_button.clicked.connect(self._on_replace_all_clicked)
        row2_layout.addWidget(self.replace_all_button)

        panel_layout.addLayout(row1_layout)
        panel_layout.addLayout(row2_layout)

        self.layout.addWidget(self.replace_panel)
        #self.replace_panel.hide() # 默认隐藏

    def _toggle_replace_panel(self):
        """切换替换面板的显示和隐藏"""
        self.replace_panel.setVisible(not self.replace_panel.isVisible())

    def _init_table(self):
        self.headers = [self.tra("文件"), self.tra("行"), self.tra("原文"), self.tra("译文"), self.tra("润文")]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 300)
        self.table.setColumnWidth(3, 300)

    def _populate_data(self, search_results: list):
        self.table.blockSignals(True) # 先关闭信号
        self.table.setRowCount(len(search_results))

        for row_idx, result_info in enumerate(search_results):
            file_path, original_row_num, item = result_info

            file_item = QTableWidgetItem(os.path.basename(file_path))
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, self.COL_FILE, file_item)

            row_num_item = QTableWidgetItem(str(original_row_num))
            row_num_item.setTextAlignment(Qt.AlignCenter)
            row_num_item.setFlags(row_num_item.flags() & ~Qt.ItemIsEditable)
            row_num_item.setData(Qt.UserRole, (file_path, item.text_index))
            self.table.setItem(row_idx, self.COL_ROW, row_num_item)

            source_item = QTableWidgetItem(item.source_text)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, self.COL_SOURCE, source_item)

            self.table.setItem(row_idx, self.COL_TRANS, QTableWidgetItem(item.translated_text))
            self.table.setItem(row_idx, self.COL_POLISH, QTableWidgetItem(item.polished_text or ''))
        
        self.table.resizeRowsToContents()
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()

        if col not in [self.COL_TRANS, self.COL_POLISH]:
            return

        ref_item = self.table.item(row, self.COL_ROW)
        if not ref_item:
            return
        
        file_path, text_index = ref_item.data(Qt.UserRole)
        new_text = item.text()

        field_name = 'translated_text' if col == self.COL_TRANS else 'polished_text'
        
        # 调试信息，可以观察到批量替换时会多次触发这里
        # print(f"Updating cache: {file_path}, index {text_index}, field {field_name}")
        
        self.cache_manager.update_item_text(
            storage_path=file_path,
            text_index=text_index,
            field_name=field_name,
            new_text=new_text
        )

    def _on_replace_all_clicked(self):
        """执行“全部替换”操作"""
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        is_case_sensitive = self.case_checkbox.isChecked()
        is_whole_word = self.whole_word_checkbox.isChecked()
        in_trans_col = self.trans_col_checkbox.isChecked()
        in_polish_col = self.polish_col_checkbox.isChecked()

        if not find_text:
            self.error_toast(self.tra("失败"), self.tra("查找内容不能为空。"))
            return
        
        if not in_trans_col and not in_polish_col:
            self.error_toast(self.tra("失败"), self.tra("请至少选择一个替换范围（译文列或润文列）。"))
            return

        target_cols = []
        if in_trans_col:
            target_cols.append(self.COL_TRANS)
        if in_polish_col:
            target_cols.append(self.COL_POLISH)

        self.table.blockSignals(True) # 开始操作前阻塞信号，提高性能
        
        replacement_count = 0
        for row in range(self.table.rowCount()):
            for col in target_cols:
                item = self.table.item(row, col)
                if not item:
                    continue
                
                original_text = item.text()
                new_text = self._perform_replace(
                    original_text, find_text, replace_text, is_case_sensitive, is_whole_word
                )

                if original_text != new_text:
                    item.setText(new_text) # 设置新文本，这将触发 itemChanged 信号
                    replacement_count += 1
        
        self.table.blockSignals(False) # 操作结束后恢复信号
        self.table.resizeRowsToContents()

        self.success_toast(
            self.tra("操作完成"), 
            self.tra(f"共找到并替换了 {replacement_count} 处。")
        )

    def _perform_replace(self, text, find, replace, case_sensitive, whole_word):
        """根据选项执行文本替换，返回新文本"""
        if not case_sensitive and not whole_word:
            # 不区分大小写，非全词匹配（使用 re.IGNORECASE）
            return re.sub(re.escape(find), replace, text, flags=re.IGNORECASE)
        
        elif case_sensitive and not whole_word:
            # 区分大小写，非全词匹配（标准 str.replace）
            return text.replace(find, replace)
        
        else: # 全词匹配（区分或不区分大小写）
            # 使用 \b 匹配单词边界
            pattern = r'\b' + re.escape(find) + r'\b'
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.sub(pattern, replace, text, flags=flags)
