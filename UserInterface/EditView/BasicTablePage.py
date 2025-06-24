from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import (QAbstractItemView, QHeaderView, QTableWidgetItem,
                             QWidget, QVBoxLayout)
from qfluentwidgets import (Action, FluentIcon as FIF, MessageBox, RoundMenu, TableWidget)

from Base.Base import Base
from ModuleFolders.Cache.CacheProject import ProjectType

# 基础表格页
class BasicTablePage(Base,QWidget):
    # 定义列索引常量
    COL_NUM = 0 # 行号
    COL_SOURCE = 1 # 原文
    COL_TRANS = 2 # 译文
    COL_POLISH = 3 # 润文

    # 修改构造函数
    def __init__(self, file_path: str, file_items: list, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName('BasicTablePage')
        
        self.file_path = file_path          # 当前表格对应的文件路径
        self.cache_manager = cache_manager  # 缓存管理器实例
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 0, 0)
        self.layout.setSpacing(0)

        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)
        
        # 使用真实数据填充表格
        self._populate_real_data(file_items)

        # 连接单元格修改信号
        self.table.itemChanged.connect(self._on_item_changed)
        # 订阅来自执行器的通用表格更新事件
        self.subscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)
        # 订阅排版完成后的表格重建事件
        self.subscribe(Base.EVENT.TABLE_FORMAT, self._on_format_and_rebuild_table) 

    # 表格属性
    def _init_table(self):
        self.headers = [self.tra("行"), self.tra("原文"), self.tra("译文"), self.tra("润文")]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        
        self.table.setWordWrap(True) #启单元格内文本自动换行
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        # 当用户拖动调整列宽时，自动重新计算并调整行高以适应内容（卡）
        #header.sectionResized.connect(self.table.resizeRowsToContents)

        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 400)
        self.table.setColumnWidth(2, 400)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    # 获取数据并填充表格
    def _populate_real_data(self, items: list):
        # 阻止信号触发，避免在填充数据时触发 _on_item_changed
        self.table.blockSignals(True)
        
        self.table.setRowCount(len(items))
        for row_idx, item_data in enumerate(items):
            # 行号列 (第0列)
            num_item = QTableWidgetItem(str(row_idx + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
            # 在行号单元格中存储 CacheItem 的唯一索引 (text_index)
            num_item.setData(Qt.UserRole, item_data.text_index)
            self.table.setItem(row_idx, 0, num_item)

            # 原文列
            source_item = QTableWidgetItem(item_data.source_text)
            # source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable) 
            self.table.setItem(row_idx, 1, source_item)
            
            # 译文、润文列 (可编辑)
            self.table.setItem(row_idx, 2, QTableWidgetItem(item_data.translated_text))
            self.table.setItem(row_idx, 3, QTableWidgetItem(item_data.polished_text or '')) # 确保 None 显示为空字符串
        
        # 填充完数据后，根据内容自动调整所有行的高度（卡）
        #self.table.resizeRowsToContents() 

        # 恢复信号
        self.table.blockSignals(False)

    # 监听用户编辑单元格
    def _on_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()

        if col not in [self.COL_SOURCE, self.COL_TRANS, self.COL_POLISH]:
            return
            
        # 获取该行对应的 CacheItem 的唯一索引
        text_index_item = self.table.item(row, 0)
        if not text_index_item:
            return 
        text_index = text_index_item.data(Qt.UserRole)

        new_text = item.text()
        
        # 根据列确定要更新的字段名
        field_name = ''
        if col == self.COL_TRANS:
            field_name = 'translated_text'
        elif col == self.COL_POLISH:
            field_name = 'polished_text'
        elif col == self.COL_SOURCE:
            field_name = 'source_text'
        
        # 调用 CacheManager 的方法来更新缓存
        self.cache_manager.update_item_text(
            storage_path=self.file_path,
            text_index=text_index,
            field_name=field_name,
            new_text=new_text
        )

    # 表格操作的右键菜单
    def _show_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self)
        
        # 检查是否有行被选中
        has_selection = bool(self.table.selectionModel().selectedRows())

        if has_selection:
            # 当有行被选中时，添加功能性操作
            menu.addAction(Action(FIF.EDIT, self.tra("翻译文本"), triggered=self._translate_text))
            menu.addAction(Action(FIF.BRUSH, self.tra("润色文本"), triggered=self._polish_text))
            menu.addAction(Action(FIF.BRUSH, self.tra("排版文本"), triggered=self._format_text))
            menu.addSeparator()

            menu.addAction(Action(FIF.COPY, self.tra("禁止翻译"), triggered=self._copy_source_to_translation))
            menu.addAction(Action(FIF.DELETE, self.tra("清空翻译"), triggered=self._clear_translation))
            menu.addAction(Action(FIF.DELETE, self.tra("清空润色"), triggered=self._clear_polishing))
            menu.addSeparator()

        # “行数”选项总是显示
        row_count = self.table.rowCount()
        row_count_action = Action(FIF.LEAF, self.tra("行数: {}").format(row_count))
        row_count_action.setEnabled(False)  # 设置为不可点击，仅作信息展示
        menu.addAction(row_count_action)

        # 在鼠标光标位置显示菜单
        global_pos = self.table.mapToGlobal(pos)
        menu.exec(global_pos)

    #  通用的表格更新函数。
    def _on_table_update(self, event, data: dict):
        """
        根据事件传递的数据，更新指定文件的指定列。
        """
        # 检查此更新是否针对当前表格
        if data.get('file_path') != self.file_path:
            return

        # 获取要更新的目标列索引和数据
        target_column_index = data.get('target_column_index')
        updated_items = data.get('updated_items', {}) # 格式: {text_index: new_text}

        # 安全检查
        if target_column_index is None or not updated_items:
            self.warning(f"表格更新数据不完整，操作中止。")
            return

        self.table.blockSignals(True)
        
        index_to_row_map = {
            self.table.item(row, self.COL_NUM).data(Qt.UserRole): row 
            for row in range(self.table.rowCount()) if self.table.item(row, self.COL_NUM)
        }

        for text_index, new_text in updated_items.items():
            if text_index in index_to_row_map:
                row = index_to_row_map[text_index]
                # 使用传入的 target_column_index 更新正确的列
                self.table.setItem(row, target_column_index, QTableWidgetItem(new_text))
        
        # 更新后，自动调整行高
        self.table.resizeRowsToContents() # <-- 重要
        self.table.blockSignals(False)

    # 表格重编排方法
    def _on_format_and_rebuild_table(self, event, data: dict):
        """
        当接收到TABLE_FORMAT事件时，使用新数据对缓存进行拼接操作并重建表格。
        """
        if data.get('file_path') != self.file_path:
            return
            
        self.info(f"接收到文件 '{self.file_path}' 的排版更新，正在重建表格...")
        
        formatted_data = data.get('updated_items')
        # 从事件中获取原始选中项的索引列表
        selected_item_indices = data.get('selected_item_indices') 

        if not formatted_data or selected_item_indices is None:
            self.error("排版更新失败：未收到有效的文本数据或原始选中项索引。")
            return

        # 调用CacheManager进行精确的“切片和拼接”操作
        updated_full_item_list = self.cache_manager.reformat_and_splice_cache(
            file_path=self.file_path,
            formatted_data=formatted_data,
            selected_item_indices=selected_item_indices
        )

        if updated_full_item_list is None:
            self.error("缓存拼接更新失败，表格更新中止。")
            return
            
        # 使用返回的、完整的item列表，重绘整个表格
        self._populate_real_data(updated_full_item_list)
        
        row_count_change = len(updated_full_item_list) - self.table.rowCount()
        self.info_toast(self.tra("排版完成"), self.tra("表格已成功更新，行数变化: {:+}").format(row_count_change))



    # 获取所有被选行的索引
    def _get_selected_rows_indices(self):
        """获取所有被选中行的索引列表"""
        return sorted(list(set(index.row() for index in self.table.selectedIndexes())))

    # 翻译文本
    def _translate_text(self):
        """处理右键菜单的“翻译文本”操作"""
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return

        # 修改软件状态
        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.TABLE_TASK
        else:
            print("❌正在执行其他任务中！")
            return

        items_to_translate = []
        for row in selected_rows:
            text_index_item = self.table.item(row, self.COL_NUM)
            source_text_item = self.table.item(row, self.COL_SOURCE)

            if text_index_item and source_text_item:
                items_to_translate.append({
                    "text_index": text_index_item.data(Qt.UserRole),
                    "source_text": source_text_item.text()
                })
        
        if not items_to_translate:
            return
        
        # 获取该文件的语言统计数据，用于确定源语言
        language_stats = self.cache_manager.project.get_file(self.file_path).language_stats

        # 发送事件到后端执行器
        self.emit(Base.EVENT.TABLE_TRANSLATE_START, {
            "file_path": self.file_path,
            "items_to_translate": items_to_translate,
            "language_stats": language_stats,
        })
        self.info_toast(self.tra("提示"), self.tra("已提交 {} 行文本的翻译任务。").format(len(items_to_translate)))

    # 润色文本
    def _polish_text(self):
        """处理右键菜单的“润色文本”操作"""
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return

        # 修改软件状态
        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.TABLE_TASK
        else:
            print("❌正在执行其他任务中！")
            return

        items_to_polish = []
        for row in selected_rows:
            text_index_item = self.table.item(row, self.COL_NUM)
            source_text_item = self.table.item(row, self.COL_SOURCE)
            translation_text_item = self.table.item(row, self.COL_TRANS)

            if text_index_item and source_text_item:
                items_to_polish.append({
                    "text_index": text_index_item.data(Qt.UserRole),
                    "source_text": source_text_item.text(),
                    "translation_text": translation_text_item.text()
                })
        
        if not items_to_polish:
            return

        # 发送事件到后端执行器
        self.emit(Base.EVENT.TABLE_POLISH_START, {
            "file_path": self.file_path,
            "items_to_polish": items_to_polish,
        })
        self.info_toast(self.tra("提示"), self.tra("已提交 {} 行文本的润色任务。").format(len(items_to_polish)))

    # 排版文本
    def _format_text(self):
        cache_file = self.cache_manager.project.get_file(self.file_path)
        if not cache_file or cache_file.file_project_type != ProjectType.TXT:
            MessageBox(self.tra("操作受限"), self.tra("“排版文本”功能当前仅支持 TXT 类型的项目文件。"), self.window()).exec() # M
            return

        selected_rows = self._get_selected_rows_indices()

        if len(selected_rows) < 2:
            MessageBox(self.tra("选择无效"), self.tra("请至少选择 2 行来进行排版操作。"), self.window()).exec() # M
            return

        if max(selected_rows) - min(selected_rows) + 1 != len(selected_rows):
            MessageBox(self.tra("选择无效"), self.tra("请选择连续的行进行排版操作。"), self.window()).exec() # M
            return

        # 修改软件状态
        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.TABLE_TASK
        else:
            print("❌正在执行其他任务中！")
            return

        items_to_format = []
        selected_item_indices = [] # 用于存储选中项的text_index
        for row in selected_rows:
            text_index_item = self.table.item(row, self.COL_NUM)
            source_text_item = self.table.item(row, self.COL_SOURCE)

            if text_index_item and source_text_item:
                text_index = text_index_item.data(Qt.UserRole)
                items_to_format.append({
                    "text_index": text_index,
                    "source_text": source_text_item.text(),
                })
                selected_item_indices.append(text_index)

        if not items_to_format:
            return

        # 发送事件到后端执行器
        self.emit(Base.EVENT.TABLE_FORMAT_START, {
            "file_path": self.file_path,
            "items_to_format": items_to_format,
            "selected_item_indices": selected_item_indices,
        })
        self.info_toast(self.tra("提示"), self.tra("已提交 {} 行文本的排版任务。").format(len(items_to_format)))

    # 复制原文到译文
    def _copy_source_to_translation(self):
        """将选中行的原文内容复制到译文行，表示无需翻译。"""
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return
        
        # 逐行设置，该操作会自动触发 itemChanged 信号，从而调用 _on_item_changed 更新缓存
        for row in selected_rows:
            source_item = self.table.item(row, self.COL_SOURCE)
            if source_item:
                source_text = source_item.text()
                
                # 更新译文列的单元格
                trans_item = self.table.item(row, self.COL_TRANS)
                if trans_item:
                    trans_item.setText(source_text)
                else:
                    # 如果译文单元格不存在，则创建一个新的
                    self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(source_text))
        
        self.info_toast(self.tra("操作完成"), self.tra("已将 {} 行的原文复制到译文。").format(len(selected_rows)))

    # 清空翻译
    def _clear_translation(self):
        selected_rows = self._get_selected_rows_indices()
        for row in selected_rows:
            # 使用常量
            item = self.table.item(row, self.COL_TRANS)
            if item:
                item.setText("")
            else:
                self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(""))

    # 清空润色
    def _clear_polishing(self):
        selected_rows = self._get_selected_rows_indices()
        for row in selected_rows:
            # 使用常量
            item = self.table.item(row, self.COL_POLISH)
            if item:
                item.setText("")
            else:
                self.table.setItem(row, self.COL_POLISH, QTableWidgetItem(""))