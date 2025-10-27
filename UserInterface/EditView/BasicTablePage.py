from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QBrush, QColor
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

    def closeEvent(self, event):
        # 在窗口关闭时，执行清理工作
        print("BasicTablePage is closing, unregistering from EventManager.")
        
        super().closeEvent(event) # 调用父类的 closeEvent

    # 修改构造函数
    def __init__(self, file_path: str, file_items: list, cache_manager, parent=None):
        super().__init__(parent)
        self.setObjectName('BasicTablePage')
        
        # 初始化 _on_item_changed 方法的处理开关
        self._item_changed_handler_enabled = True

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

        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 400)
        self.table.setColumnWidth(2, 400)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    # 获取数据并填充表格
    def _populate_real_data(self, items: list):
        # 在批量填充数据前，关闭 _on_item_changed 的处理逻辑
        self._item_changed_handler_enabled = False
        try:
            # 定义高亮颜色：半透明浅绿色
            highlight_brush = QBrush(QColor(144, 238, 144, 100))
            
            self.table.setRowCount(len(items))
            for row_idx, item_data in enumerate(items):
                # 行号列 (第0列)
                num_item = QTableWidgetItem(str(row_idx + 1))
                num_item.setTextAlignment(Qt.AlignCenter)
                num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
                num_item.setData(Qt.UserRole, item_data.text_index)
                self.table.setItem(row_idx, 0, num_item)

                # 原文列
                source_item = QTableWidgetItem(item_data.source_text)
                self.table.setItem(row_idx, 1, source_item)
                
                # 译文、润文列 (可编辑)
                trans_item = QTableWidgetItem(item_data.translated_text)
                polish_item = QTableWidgetItem(item_data.polished_text or '')
                self.table.setItem(row_idx, 2, trans_item)
                self.table.setItem(row_idx, 3, polish_item)

                # 检查是否存在 extra 字典以及对应的标记
                if item_data.extra:
                    # 如果翻译文本被标记，则高亮第2列（译文）
                    if item_data.extra.get('language_mismatch_translation', False):
                        trans_item.setBackground(highlight_brush)
                    
                    # 如果润色文本被标记，则高亮第3列（润文）
                    if item_data.extra.get('language_mismatch_polish', False):
                        polish_item.setBackground(highlight_brush)

        finally:
            # 无论是否发生异常，都确保在操作结束后重新打开开关
            self._item_changed_handler_enabled = True

    # 监听用户编辑单元格
    def _on_item_changed(self, item: QTableWidgetItem):
        # 检查开关状态，如果为关闭，则不执行任何操作
        if not self._item_changed_handler_enabled:
            return

        row = item.row()
        col = item.column()

        if col not in [self.COL_SOURCE, self.COL_TRANS, self.COL_POLISH]:
            return
            
        text_index_item = self.table.item(row, 0)
        if not text_index_item:
            return 
        text_index = text_index_item.data(Qt.UserRole)

        new_text = item.text()
        
        field_name = ''
        if col == self.COL_TRANS:
            field_name = 'translated_text'
        elif col == self.COL_POLISH:
            field_name = 'polished_text'
        elif col == self.COL_SOURCE:
            field_name = 'source_text'
        
        self.cache_manager.update_item_text(
            storage_path=self.file_path,
            text_index=text_index,
            field_name=field_name,
            new_text=new_text
        )

    # 表格操作的右键菜单
    def _show_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self)
        has_selection = bool(self.table.selectionModel().selectedRows())
        if has_selection:
            menu.addAction(Action(FIF.EXPRESSIVE_INPUT_ENTRY, self.tra("翻译文本"), triggered=self._translate_text))
            menu.addAction(Action(FIF.BRUSH, self.tra("润色文本"), triggered=self._polish_text))
            menu.addSeparator()
            menu.addAction(Action(FIF.COPY, self.tra("禁止翻译"), triggered=self._copy_source_to_translation))
            menu.addAction(Action(FIF.DELETE, self.tra("清空翻译"), triggered=self._clear_translation))
            menu.addAction(Action(FIF.DELETE, self.tra("清空润色"), triggered=self._clear_polishing))
            menu.addSeparator()
        row_count = self.table.rowCount()
        row_count_action = Action(FIF.LEAF, self.tra("行数: {}").format(row_count))
        row_count_action.setEnabled(False)
        menu.addAction(row_count_action)
        global_pos = self.table.mapToGlobal(pos)
        menu.exec(global_pos)


    def _on_table_update(self, event, data: dict):
        """
        根据事件传递的数据，更新指定文件的指定列。
        """
        if data.get('file_path') != self.file_path:
            return

        target_column_index = data.get('target_column_index')
        updated_items = data.get('updated_items', {})

        if target_column_index is None or not updated_items:
            self.warning(f"表格更新数据不完整，操作中止。")
            return

        # 根据列索引确定要更新的字段名
        field_name_map = {
            self.COL_TRANS: 'translated_text',
            self.COL_POLISH: 'polished_text'
        }
        field_name = field_name_map.get(target_column_index)
        if not field_name:
            self.warning(f"无效的目标列索引: {target_column_index}")
            return

        # 在批量更新前关闭开关，操作结束后再打开
        self._item_changed_handler_enabled = False
        try:
            index_to_row_map = {
                self.table.item(row, self.COL_NUM).data(Qt.UserRole): row 
                for row in range(self.table.rowCount()) if self.table.item(row, self.COL_NUM)
            }

            for text_index, new_text in updated_items.items():
                if text_index in index_to_row_map:
                    row = index_to_row_map[text_index]
                    
                    # 更新UI表格
                    self.table.setItem(row, target_column_index, QTableWidgetItem(new_text))

                    # 更新CacheManager中的数据模型
                    self.cache_manager.update_item_text(
                        storage_path=self.file_path,
                        text_index=text_index,
                        field_name=field_name,
                        new_text=new_text
                    )
            
            self.table.resizeRowsToContents()
        finally:
            self._item_changed_handler_enabled = True

    def _get_selected_rows_indices(self):
        """获取所有被选中行的索引列表"""
        return sorted(list(set(index.row() for index in self.table.selectedIndexes())))

    def _translate_text(self):
        """处理右键菜单的“翻译文本”操作"""
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return

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
        
        language_stats = self.cache_manager.project.get_file(self.file_path).language_stats

        self.emit(Base.EVENT.TABLE_TRANSLATE_START, {
            "file_path": self.file_path,
            "items_to_translate": items_to_translate,
            "language_stats": language_stats,
        })
        self.info_toast(self.tra("提示"), self.tra("已提交 {} 行文本的翻译任务。").format(len(items_to_translate)))

    def _polish_text(self):
        """处理右键菜单的“润色文本”操作"""
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return

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

        self.emit(Base.EVENT.TABLE_POLISH_START, {
            "file_path": self.file_path,
            "items_to_polish": items_to_polish,
        })
        self.info_toast(self.tra("提示"), self.tra("已提交 {} 行文本的润色任务。").format(len(items_to_polish)))

    def _copy_source_to_translation(self):
        """将选中行的原文内容复制到译文行，表示无需翻译。"""
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
            return
        
        for row in selected_rows:
            source_item = self.table.item(row, self.COL_SOURCE)
            if source_item:
                source_text = source_item.text()
                trans_item = self.table.item(row, self.COL_TRANS)
                if trans_item:
                    trans_item.setText(source_text)
                else:
                    self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(source_text))
        
        self.info_toast(self.tra("操作完成"), self.tra("已将 {} 行的原文复制到译文。").format(len(selected_rows)))

    def _clear_translation(self):
        selected_rows = self._get_selected_rows_indices()
        for row in selected_rows:
            item = self.table.item(row, self.COL_TRANS)
            if item:
                item.setText("")
            else:
                self.table.setItem(row, self.COL_TRANS, QTableWidgetItem(""))

    def _clear_polishing(self):
        selected_rows = self._get_selected_rows_indices()
        for row in selected_rows:
            item = self.table.item(row, self.COL_POLISH)
            if item:
                item.setText("")
            else:
                self.table.setItem(row, self.COL_POLISH, QTableWidgetItem(""))