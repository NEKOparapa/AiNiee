from collections import defaultdict
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem, 
                             QHeaderView, QAbstractItemView)
from qfluentwidgets import TableWidget, RoundMenu, Action, FluentIcon
from ModuleFolders.Base.Base import Base

class CheckResultPage(Base, QWidget):
    def __init__(self, results: list, cache_manager=None, parent=None):
        super().__init__(parent)
        self.results = results
        self.cache_manager = cache_manager
        self.setObjectName("CheckResultPage")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.table = TableWidget(self)
        self.layout.addWidget(self.table)
        
        self._init_table()
        self._populate_data()

        # 连接表格内容改变信号（用于手动编辑）
        self.table.itemChanged.connect(self._on_item_changed)
        
        #订阅表格更新事件 (用于接收翻译完成后的回调)
        self.subscribe(Base.EVENT.TABLE_UPDATE, self._on_table_update)

    def _init_table(self):
        headers = [
            self.tra("行"),
            self.tra("错误"),
            self.tra("原文"),
            self.tra("检测文本")
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderRadius(8)
        
        # 设置选择模式
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # 列宽调整
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        
        # 允许点击表头排序，但不默认显示排序箭头
        header.setSortIndicatorShown(False)

        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 300)

    def _populate_data(self):
        self.table.blockSignals(True)
        
        self.table.setSortingEnabled(False) 
        self.table.setRowCount(len(self.results))
        
        for i, data in enumerate(self.results):
            # 尝试将行号转为int，以便正确排序 (1, 2, 10 而不是 1, 10, 2)
            row_id_raw = data.get("row_id", "")
            item_id = QTableWidgetItem()
            
            # 设置显示的文本
            item_id.setText(str(row_id_raw))
            
            # 尝试设置数值数据用于排序
            try:
                # 假设 row_id 是纯数字或可以转为数字
                sort_val = int(row_id_raw)
                item_id.setData(Qt.DisplayRole, sort_val) 
            except (ValueError, TypeError):
                pass
                
            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable) 
            
            # 存储元数据
            meta_data = {
                "file_path": data.get("file_path"),
                "text_index": data.get("text_index"),
                "target_field": data.get("target_field"),
                "original_data_index": i
            }
            item_id.setData(Qt.UserRole, meta_data)
            self.table.setItem(i, 0, item_id)
            
            # 错误类型
            item_type = QTableWidgetItem(data.get("error_type", ""))
            item_type.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(i, 1, item_type)
            
            # 原文
            item_src = QTableWidgetItem(data.get("source", ""))
            item_src.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(i, 2, item_src)
            
            # 检测文本
            item_check = QTableWidgetItem(data.get("check_text", ""))
            item_check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            self.table.setItem(i, 3, item_check)
            
        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        """处理用户手动编辑单元格"""
        if item.column() != 3:
            return

        row = item.row()
        id_item = self.table.item(row, 0)
        if not id_item: return
        meta_data = id_item.data(Qt.UserRole)
        
        if not meta_data or not self.cache_manager:
            return

        new_text = item.text()
        file_path = meta_data["file_path"]
        text_index = meta_data["text_index"]
        target_field = meta_data["target_field"]

        if file_path and text_index is not None:
            # 更新缓存
            self.cache_manager.update_item_text(
                storage_path=file_path,
                text_index=text_index,
                field_name=target_field,
                new_text=new_text
            )
            
            # 更新内部数据源，防止排序后数据丢失
            if "original_data_index" in meta_data:
                self.results[meta_data["original_data_index"]]["check_text"] = new_text

    # 处理后台翻译完成后的UI更新
    def _on_table_update(self, event, data: dict):
        """
        接收 TABLE_UPDATE 事件，更新表格中的翻译/润色内容。
        data 结构预期: {'file_path': str, 'target_column_index': int, 'updated_items': {index: text}}
        """
        updated_file_path = data.get('file_path')
        target_column_index = data.get('target_column_index') # 2=翻译, 3=润色
        updated_items = data.get('updated_items', {})

        if not updated_file_path or not updated_items:
            return

        # 映射 BasicTablePage 的列索引到字段名
        # 2 (COL_TRANS) -> translated_text
        # 3 (COL_POLISH) -> polished_text
        field_map = {
            2: "translated_text",
            3: "polished_text"
        }
        updated_field_type = field_map.get(target_column_index)

        if not updated_field_type:
            return

        # 暂时屏蔽信号以提高性能并防止触发 _on_item_changed
        self.table.blockSignals(True)
        try:
            # 遍历当前表格的所有行，寻找匹配的条目
            # 注意：由于表格可能经过排序或筛选，我们必须遍历所有可视行
            for row in range(self.table.rowCount()):
                id_item = self.table.item(row, 0)
                if not id_item: continue
                
                meta_data = id_item.data(Qt.UserRole)
                if not meta_data: continue

                # 检查文件路径是否匹配
                if meta_data.get("file_path") != updated_file_path:
                    continue

                # 检查字段类型是否匹配
                # 只有当错误列表中显示的字段 (target_field) 与当前更新的字段一致时才更新
                # 例如：我们在检查译文错误，此时后台更新了译文，则刷新。
                if meta_data.get("target_field") != updated_field_type:
                    continue

                # 检查行索引是否在更新列表中
                text_index = meta_data.get("text_index")
                if text_index in updated_items:
                    new_text = updated_items[text_index]
                    
                    # 更新 UI (第3列是“检测文本”)
                    check_text_item = self.table.item(row, 3)
                    if check_text_item:
                        check_text_item.setText(new_text)

                    # 更新内部数据源 results
                    if "original_data_index" in meta_data:
                        self.results[meta_data["original_data_index"]]["check_text"] = new_text
                        
                        # 可选：如果错误类型是"条目未翻译"，更新后可以考虑移除该错误描述或标记为已修复
                        # 这里简单处理，仅更新文本
        finally:
            self.table.blockSignals(False)

    def _show_context_menu(self, pos: QPoint):
        menu = RoundMenu(parent=self)
        selected_rows = self.table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0
        
        # 翻译文本选项
        translate_action = Action(FluentIcon.EXPRESSIVE_INPUT_ENTRY, self.tra("翻译选中项"), self)
        translate_action.setEnabled(has_selection)
        translate_action.triggered.connect(self._translate_selected_rows)
        menu.addAction(translate_action)

        menu.addSeparator()

        delete_action = Action(FluentIcon.DELETE, self.tra("删除选中行"), self)
        delete_action.setEnabled(has_selection)
        delete_action.triggered.connect(self._delete_selected_rows)
        menu.addAction(delete_action)
        
        menu.exec(self.table.mapToGlobal(pos))

    def _translate_selected_rows(self):
        """将选中的错误行发送去翻译"""
        if Base.work_status == Base.STATUS.IDLE:
            Base.work_status = Base.STATUS.TABLE_TASK
        else:
            self.warning(self.tra("正在执行其他任务中！"))
            return

        selected_rows = sorted(list(set(index.row() for index in self.table.selectedIndexes())))
        if not selected_rows:
            return

        # 1. 按文件路径对选中的行进行分组
        tasks_by_file = defaultdict(list)
        
        for row in selected_rows:
            id_item = self.table.item(row, 0) 
            src_item = self.table.item(row, 2) 
            
            if not id_item or not src_item:
                continue
                
            meta_data = id_item.data(Qt.UserRole)
            file_path = meta_data.get("file_path")
            text_index = meta_data.get("text_index")
            source_text = src_item.text()
            
            # 只有当目标字段是 translated_text 时才允许翻译
            # (如果是 polished_text，通常应该调用润色，这里简化逻辑，暂只处理翻译)
            target_field = meta_data.get("target_field")
            
            if file_path and text_index is not None:
                # 记录任务
                tasks_by_file[file_path].append({
                    "text_index": text_index,
                    "source_text": source_text
                })

        # 2. 遍历分组，发送任务
        count = 0
        for file_path, items_to_translate in tasks_by_file.items():
            if not items_to_translate:
                continue
            
            file_obj = self.cache_manager.project.get_file(file_path)
            language_stats = file_obj.language_stats if file_obj else None

            self.emit(Base.EVENT.TABLE_TRANSLATE_START, {
                "file_path": file_path,
                "items_to_translate": items_to_translate,
                "language_stats": language_stats,
            })
            count += len(items_to_translate)
        
        if count > 0:
            self.info_toast(self.tra("提示"), self.tra("已提交 {} 个条目的翻译任务。").format(count))

    def _delete_selected_rows(self):
        # 删除时需要先关闭排序，否则删除过程中索引可能会变动导致异常
        current_sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()), reverse=True)
        
        if selected_rows:
            for row in selected_rows:
                self.table.removeRow(row)
        
        # 恢复排序状态
        self.table.setSortingEnabled(current_sorting)