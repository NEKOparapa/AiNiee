import os
import re 
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem, 
                             QAbstractItemView, QHeaderView, QHBoxLayout, QSpacerItem, QSizePolicy)

from qfluentwidgets import (TableWidget, PrimaryPushButton, LineEdit, StrongBodyLabel,
                            CheckBox)
from Base.Base import Base


class SearchResultPage(Base, QWidget):
    # ===== 列索引常量 ===== #
    COL_FILE = 0   # 文件名列
    COL_ROW = 1    # 行号列
    COL_SOURCE = 2 # 原文列
    COL_TRANS = 3  # 译文列
    COL_POLISH = 4 # 润文列

    def __init__(self, search_results: list, cache_manager, search_params: dict, parent=None):
        """搜索结果展示页面构造函数
        
        Args:
            search_results: 搜索结果列表，格式为[(文件路径, 行号, 文本项)]
            cache_manager: 缓存管理器实例，用于数据持久化
            search_params: 包含 'query', 'is_regex', 'scope' 的字典
            parent: 父组件
        """
        super().__init__(parent)
        self.setObjectName('SearchResultPage')
        
        self.cache_manager = cache_manager  # 缓存管理器实例
        self.search_params = search_params  # 存储搜索参数
        
        # 主布局
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)  # 设置边距
        self.layout.setSpacing(10)  # 设置组件间距

        # 初始化批量替换面板
        self._init_replace_panel()

        # 初始化表格组件
        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)
        
        # 填充表格数据
        self._populate_data(search_results)

        # 连接表格内容变更信号
        self.table.itemChanged.connect(self._on_item_changed)

    def _init_replace_panel(self):
        """初始化批量替换面板（包含查找/替换输入框、选项和操作按钮）"""
        self.replace_panel = QWidget(self)
        self.replace_panel.setObjectName("replacePanel")
        
        # 面板布局
        panel_layout = QVBoxLayout(self.replace_panel)
        panel_layout.setContentsMargins(0, 0, 0, 5)
        panel_layout.setSpacing(8)

        # 创建两行布局：第一行输入框，第二行选项和按钮
        row1_layout = QHBoxLayout()
        row2_layout = QHBoxLayout()

        # ===== 第一行：查找和替换输入 ===== #
        row1_layout.addWidget(StrongBodyLabel(self.tra("查找内容:"), self))
        self.find_input = LineEdit(self)
        self.find_input.setPlaceholderText(self.tra("输入搜索内容...")) 
        row1_layout.addWidget(self.find_input)
        
        row1_layout.addSpacing(20)  # 添加间距

        row1_layout.addWidget(StrongBodyLabel(self.tra("替换为:"), self))
        self.replace_input = LineEdit(self)
        self.replace_input.setPlaceholderText(self.tra("输入替换后的文本..."))
        row1_layout.addWidget(self.replace_input)
        
        # ===== 第二行：替换选项和操作 ===== #
        row2_layout.addWidget(StrongBodyLabel(self.tra("选项:"), self))
        # 大小写匹配复选框
        self.case_checkbox = CheckBox(self.tra("区分大小写"), self)
        # 全词匹配复选框
        self.whole_word_checkbox = CheckBox(self.tra("全词匹配"), self)
        # 正则表达式模式复选框
        self.regex_checkbox = CheckBox(self.tra("正则模式"), self)
        
        row2_layout.addWidget(self.case_checkbox)
        row2_layout.addWidget(self.whole_word_checkbox)
        row2_layout.addWidget(self.regex_checkbox)
        
        row2_layout.addSpacing(15)  # 添加间距
        
        # 替换范围选择
        row2_layout.addWidget(StrongBodyLabel(self.tra("范围:"), self))
        self.trans_col_checkbox = CheckBox(self.tra("译文列"), self)
        self.polish_col_checkbox = CheckBox(self.tra("润文列"), self)
        self.trans_col_checkbox.setChecked(True)  # 默认选中译文列
        row2_layout.addWidget(self.trans_col_checkbox)
        row2_layout.addWidget(self.polish_col_checkbox)

        # 添加弹性空间使按钮靠右
        row2_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # 全部替换按钮
        self.replace_all_button = PrimaryPushButton(self.tra("全部替换"), self)
        row2_layout.addWidget(self.replace_all_button)

        # 将两行布局添加到面板
        panel_layout.addLayout(row1_layout)
        panel_layout.addLayout(row2_layout)

        # 添加面板到主布局
        self.layout.addWidget(self.replace_panel)
        
        # ===== 信号连接 ===== #
        # 正则模式切换时更新UI状态
        self.regex_checkbox.toggled.connect(self._on_regex_toggled)
        # 绑定全部替换按钮点击事件
        self.replace_all_button.clicked.connect(self._on_replace_all_clicked)

    def _on_regex_toggled(self, is_checked: bool):
        """正则模式复选框状态变化处理
        
        当启用正则模式时：
        1. 禁用全词匹配选项（二者互斥）
        2. 自动取消全词匹配的选中状态
        """
        self.whole_word_checkbox.setEnabled(not is_checked)
        if is_checked:
            self.whole_word_checkbox.setChecked(False)

    def _init_table(self):
        """初始化表格控件（设置列名、样式和交互行为）"""
        # 表格列标题（已翻译）
        self.headers = [
            self.tra("文件"), 
            self.tra("行"), 
            self.tra("原文"), 
            self.tra("译文"), 
            self.tra("润文")
        ]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()  # 隐藏行号列
        self.table.setAlternatingRowColors(True)  # 启用斑马纹
        self.table.setWordWrap(True)  # 允许文本换行
        #self.table.setBorderVisible(True)  # 显示边框
        self.table.setBorderRadius(8)  # 圆角边框
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 扩展选择模式
        
        # 设置表头行为
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)  # 可交互调整列宽
        header.setStretchLastSection(True)  # 最后一列自动拉伸
        
        # 设置初始列宽
        self.table.setColumnWidth(0, 150)  # 文件名列
        self.table.setColumnWidth(1, 55)   # 行号列
        self.table.setColumnWidth(2, 300)  # 原文列
        self.table.setColumnWidth(3, 300)  # 译文列

    def _populate_data(self, search_results: list):
        """将搜索结果填充到表格中
        
        Args:
            search_results: 搜索结果列表，格式为[(文件路径, 行号, 文本项)]
        """
        # 阻塞信号防止频繁触发itemChanged
        self.table.blockSignals(True)

        # 定义高亮颜色
        highlight_brush = QBrush(QColor(144, 238, 144, 100))
        
        # 设置表格行数
        self.table.setRowCount(len(search_results))

        # 遍历所有搜索结果
        for row_idx, result_info in enumerate(search_results):
            file_path, original_row_num, item = result_info

            # 文件名项（不可编辑）
            file_item = QTableWidgetItem(os.path.basename(file_path))
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, self.COL_FILE, file_item)

            # 行号项（不可编辑，存储原始数据）
            row_num_item = QTableWidgetItem(str(original_row_num))
            row_num_item.setTextAlignment(Qt.AlignCenter)  # 居中对齐
            row_num_item.setFlags(row_num_item.flags() & ~Qt.ItemIsEditable)
            # 存储元数据：(文件路径, 文本索引)
            row_num_item.setData(Qt.UserRole, (file_path, item.text_index))
            self.table.setItem(row_idx, self.COL_ROW, row_num_item)

            # 原文项（不可编辑）
            source_item = QTableWidgetItem(item.source_text)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, self.COL_SOURCE, source_item)

            # 译文项（可编辑）
            trans_item = QTableWidgetItem(item.translated_text)
            self.table.setItem(row_idx, self.COL_TRANS, trans_item)
            # 润文项（可编辑）
            polish_item = QTableWidgetItem(item.polished_text or '')
            self.table.setItem(row_idx, self.COL_POLISH, polish_item)

            # 检查并应用高亮
            if item.extra:
                if item.extra.get('language_mismatch_translation', False):
                    trans_item.setBackground(highlight_brush)
                if item.extra.get('language_mismatch_polish', False):
                    polish_item.setBackground(highlight_brush)
        
        # 自动调整行高以适应内容
        self.table.resizeRowsToContents()
        # 恢复信号连接
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        """处理表格内容变更事件（用户编辑译文/润文列时触发）
        
        1. 获取被修改的单元格位置
        2. 通过关联的行号项获取元数据
        3. 更新缓存管理器中的对应数据
        """
        row = item.row()
        col = item.column()

        # 仅处理译文列(3)和润文列(4)的变更
        if col not in [self.COL_TRANS, self.COL_POLISH]:
            return

        # 获取关联的行号项（存储元数据）
        ref_item = self.table.item(row, self.COL_ROW)
        if not ref_item:
            return
        
        # 解析元数据：(文件路径, 文本索引)
        file_path, text_index = ref_item.data(Qt.UserRole)
        new_text = item.text()  # 获取修改后的文本

        # 确定修改的是译文还是润文
        field_name = 'translated_text' if col == self.COL_TRANS else 'polished_text'
        
        # 更新缓存数据
        self.cache_manager.update_item_text(
            storage_path=file_path,
            text_index=text_index,
            field_name=field_name,
            new_text=new_text
        )

    def _on_replace_all_clicked(self):
        """执行全部替换操作
        步骤：
        1. 验证输入有效性
        2. 获取所有替换选项
        3. 遍历目标单元格
        4. 执行替换并更新UI
        5. 显示操作结果
        """
        # 获取用户输入和选项
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        is_case_sensitive = self.case_checkbox.isChecked()
        is_whole_word = self.whole_word_checkbox.isChecked()
        is_regex = self.regex_checkbox.isChecked()
        in_trans_col = self.trans_col_checkbox.isChecked()
        in_polish_col = self.polish_col_checkbox.isChecked()

        # 输入验证
        if not find_text:
            self.error_toast(self.tra("失败"), self.tra("查找内容不能为空。"))
            return
        
        if not in_trans_col and not in_polish_col:
            self.error_toast(self.tra("失败"), self.tra("请至少选择一个替换范围（译文列或润文列）。"))
            return

        # 正则表达式预编译验证
        if is_regex:
            try:
                # 尝试编译正则表达式（带大小写敏感标志）
                flags = 0 if is_case_sensitive else re.IGNORECASE
                re.compile(find_text, flags)
            except re.error as e:
                self.error_toast(self.tra("替换失败"), self.tra(f"无效的正则表达式：{e}"))
                return

        # 确定目标列索引
        target_cols = []
        if in_trans_col:
            target_cols.append(self.COL_TRANS)
        if in_polish_col:
            target_cols.append(self.COL_POLISH)

        # 阻塞表格信号
        self.table.blockSignals(True)
        
        replacement_count = 0  # 替换计数器
        # 遍历所有行和目标列
        for row in range(self.table.rowCount()):
            for col in target_cols:
                item = self.table.item(row, col)
                if not item:
                    continue
                
                original_text = item.text()
                # 执行实际替换操作
                new_text = self._perform_replace(
                    original_text, find_text, replace_text, 
                    is_case_sensitive, is_whole_word, is_regex
                )

                # 更新发生变化的单元格
                if original_text != new_text:
                    # 1. 更新UI
                    item.setText(new_text)
                    replacement_count += 1
                    
                    # 2. 获取元数据
                    ref_item = self.table.item(row, self.COL_ROW)
                    if ref_item:
                        file_path, text_index = ref_item.data(Qt.UserRole)
                        
                        # 3. 确定修改的字段
                        field_name = 'translated_text' if col == self.COL_TRANS else 'polished_text'
                        
                        # 4. 调用缓存管理器更新数据
                        self.cache_manager.update_item_text(
                            storage_path=file_path,
                            text_index=text_index,
                            field_name=field_name,
                            new_text=new_text
                        )
        
        # 恢复信号连接并更新UI
        self.table.blockSignals(False)
        self.table.resizeRowsToContents()  # 重新调整行高

        # 显示操作结果
        self.success_toast(
            self.tra("操作完成"), 
            self.tra(f"共找到并替换了 {replacement_count} 处。")
        )

    def _perform_replace(self, text, find, replace, case_sensitive, whole_word, is_regex):
        """执行实际文本替换逻辑
        
        支持三种模式：
        1. 正则表达式模式
        2. 全词匹配模式
        3. 普通文本替换模式
        
        Returns:
            str: 替换后的新文本
        """
        # 正则表达式模式
        if is_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.sub(find, replace, text, flags=flags)

        # 非正则模式
        flags = 0 if case_sensitive else re.IGNORECASE
        
        # 全词匹配模式
        if whole_word:
            pattern = r'\b' + re.escape(find) + r'\b'
            return re.sub(pattern, replace, text, flags=flags)
        # 普通文本替换
        else:
            if case_sensitive:
                # 区分大小写 - 使用高效的原生替换
                return text.replace(find, replace)
            else:
                # 不区分大小写 - 使用正则替换
                return re.sub(re.escape(find), replace, text, flags=flags)