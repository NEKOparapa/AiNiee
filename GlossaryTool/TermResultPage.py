import os
import json
import uuid
import copy
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem,
                             QAbstractItemView, QHeaderView, QHBoxLayout,
                             QSpacerItem, QSizePolicy, QFileDialog)

from qfluentwidgets import (TableWidget, PrimaryPushButton, FluentIcon,
                              RoundMenu, Action, MessageBox)
from GlossaryTool.Base import Base

class TermResultPage(QWidget, Base):
    """
    用于显示术语提取结果的页面。
    """
    # 定义列索引常量
    COL_TERM = 0
    COL_COUNT = 1
    COL_TYPE = 2
    COL_CONTEXT = 3
    COL_FILE = 4

    def __init__(self, extraction_results: list, parent=None):
        super().__init__(parent) # Base doesn't need init args usually, but QWidget might
        # QWidget.__init__(self, parent) # Base init handles nothing, so we rely on QWidget
        self.setObjectName('TermResultPage')

        # 存储提取结果以供后续使用
        # 使用深拷贝防止引用问题
        self.extraction_results = copy.deepcopy(extraction_results)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(10)

        self._init_toolbar()

        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)

        self._populate_data(extraction_results)

    def _init_toolbar(self):
        """初始化顶部工具栏"""
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # 导出术语提取数据按钮
        self.export_button = PrimaryPushButton(FluentIcon.SAVE, self.tra("导出术语提取数据"), self)
        self.export_button.clicked.connect(self._on_export_data)
        toolbar_layout.addWidget(self.export_button)

        # 删除选中行按钮
        self.delete_button = PrimaryPushButton(FluentIcon.DELETE, self.tra("删除选中"), self)
        self.delete_button.clicked.connect(self._delete_selected_rows)
        toolbar_layout.addWidget(self.delete_button)

        # 独立版暂不支持自动翻译功能，因此隐藏此按钮
        # self.translate_save_button = PrimaryPushButton(FluentIcon.LANGUAGE, self.tra("翻译后保存到术语表"), self)
        # self.translate_save_button.clicked.connect(self._on_translate_and_save)
        # toolbar_layout.addWidget(self.translate_save_button)

        self.save_button = PrimaryPushButton(FluentIcon.DICTIONARY_ADD, self.tra("保存到术语表"), self)
        self.save_button.clicked.connect(self._on_save_to_glossary)
        toolbar_layout.addWidget(self.save_button)

        self.layout.addLayout(toolbar_layout)

    def _init_table(self):
        """初始化表格样式和表头"""
        self.headers = [self.tra("术语"), self.tra("出现次数"), self.tra("类型"), self.tra("所在原文"), self.tra("来源文件")]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        
        # 允许编辑（双击或按键）
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        # 监听单元格修改事件
        self.table.itemChanged.connect(self._on_item_changed)

        # 启用多行选择
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(self.COL_TERM, 180)
        self.table.setColumnWidth(self.COL_COUNT, 90)
        self.table.setColumnWidth(self.COL_TYPE, 120)
        self.table.setColumnWidth(self.COL_CONTEXT, 400)
        self.table.setColumnWidth(self.COL_FILE, 180)

        # 自定义上下文菜单策略并连接信号
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def _populate_data(self, results: list):
        """用提取结果填充表格"""
        # 暂时断开 itemChanged 信号，避免填充时触发
        try:
            self.table.itemChanged.disconnect(self._on_item_changed)
        except TypeError:
            pass  # 如果尚未连接，忽略错误

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        for row_idx, result in enumerate(results):
            # 确保每个结果都有唯一ID，用于追踪修改
            if '_id' not in result:
                result['_id'] = str(uuid.uuid4())
            unique_id = result['_id']

            term_item = QTableWidgetItem(result["term"])
            # 将唯一ID存储在术语列的 UserRole 中
            term_item.setData(Qt.UserRole, unique_id)
            
            type_item = QTableWidgetItem(result["type"])
            # 简单的截断处理
            context_text = result.get("context", "")
            if len(context_text) > 100: context_text = context_text[:100] + "..."
            context_item = QTableWidgetItem(context_text)
            
            file_path = result.get("file_path", "")
            file_item = QTableWidgetItem(os.path.basename(file_path) if file_path else "")
            # 文件列设为只读
            file_item.setFlags(file_item.flags() & ~Qt.ItemIsEditable)
            
            count = result.get('count', 1)
            count_item = QTableWidgetItem()
            count_item.setData(Qt.DisplayRole, count)
            count_item.setData(Qt.EditRole, count)
            count_item.setTextAlignment(Qt.AlignCenter)
            # 出现次数设为只读
            count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
            
            self.table.setItem(row_idx, self.COL_TERM, term_item)
            self.table.setItem(row_idx, self.COL_COUNT, count_item)
            self.table.setItem(row_idx, self.COL_TYPE, type_item)
            self.table.setItem(row_idx, self.COL_CONTEXT, context_item)
            self.table.setItem(row_idx, self.COL_FILE, file_item)
            
        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(self.COL_COUNT, Qt.DescendingOrder)
        
        # 恢复 itemChanged 信号连接
        self.table.itemChanged.connect(self._on_item_changed)

    def _on_item_changed(self, item):
        """处理单元格编辑完成后的数据更新"""
        row = item.row()
        col = item.column()
        
        # 获取该行的术语项（第0列），从中获取唯一ID
        term_item = self.table.item(row, self.COL_TERM)
        if not term_item:
            return
            
        unique_id = term_item.data(Qt.UserRole)
        if not unique_id:
            return

        # 根据ID查找对应的数据项
        target_result = next((r for r in self.extraction_results if r.get('_id') == unique_id), None)
        
        if target_result:
            new_value = item.text()
            if col == self.COL_TERM:
                target_result['term'] = new_value
            elif col == self.COL_TYPE:
                target_result['type'] = new_value
            elif col == self.COL_CONTEXT:
                target_result['context'] = new_value

    def _show_context_menu(self, pos: QPoint):
        """当在表格上右键时，显示上下文菜单"""
        menu = RoundMenu(parent=self)

        # 检查是否有行被选中
        selected_rows = self.table.selectionModel().selectedRows()
        has_selection = bool(selected_rows)

        # 添加“删除行”选项
        delete_action = Action(FluentIcon.DELETE, self.tra("删除选中行"))
        delete_action.setEnabled(has_selection) # 仅在有选中行时启用
        delete_action.triggered.connect(self._delete_selected_rows)
        menu.addAction(delete_action)
        
        # 添加“保存选中行”选项
        save_selected_action = Action(FluentIcon.SAVE, self.tra("保存选中行到术语表"))
        save_selected_action.setEnabled(has_selection)
        save_selected_action.triggered.connect(lambda: self._on_save_to_glossary(only_selected=True))
        menu.addAction(save_selected_action)

        menu.addSeparator()

        # 添加“行数信息”选项
        row_count = self.table.rowCount()
        row_count_action = Action(FluentIcon.INFO, self.tra("总行数: {}").format(row_count))
        row_count_action.setEnabled(False)  # 仅作信息展示，不可点击
        menu.addAction(row_count_action)

        # 在鼠标光标位置显示菜单
        global_pos = self.table.mapToGlobal(pos)
        menu.exec(global_pos)

    def _delete_selected_rows(self):
        """删除所有选中的行"""
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            return

        # 获取所有不重复的选中行号（视图行号）
        rows_to_delete = sorted(list(set(index.row() for index in selected_indexes)))
        
        if not rows_to_delete:
            return

        # 弹出确认对话框
        confirm_msg = MessageBox(
            self.tra("确认删除"),
            self.tra("您确定要删除选中的 {} 行吗？此操作不可撤销。").format(len(rows_to_delete)),
            self.window()
        )
        if not confirm_msg.exec():
            return # 用户点击了取消

        # 收集要删除的 ID
        ids_to_delete = set()
        for row in rows_to_delete:
            term_item = self.table.item(row, self.COL_TERM)
            if term_item:
                unique_id = term_item.data(Qt.UserRole)
                if unique_id:
                    ids_to_delete.add(unique_id)

        # 从视图（表格）中删除，从后往前删
        for row in reversed(rows_to_delete):
            self.table.removeRow(row)

        # 从数据模型中删除
        self.extraction_results = [r for r in self.extraction_results if r.get('_id') not in ids_to_delete]

        self.success_toast(
            self.tra("操作成功"),
            self.tra("已成功删除 {} 行。").format(len(rows_to_delete))
        )

    def _on_export_data(self):
        """处理“导出术语提取数据”按钮点击事件"""
        if not self.extraction_results:
            self.warning_toast(self.tra("提示"), self.tra("没有可导出的术语。"))
            return

        # 准备导出的数据，格式与术语表配置一致
        export_data = []
        for result in self.extraction_results:
            export_data.append({
                "src": result['term'],
                "dst": "",  # 未翻译状态
                "info": result['type'],
                "count": result.get('count', 1),
                "context": result.get('context', "")
            })

        # 默认文件名
        default_filename = "术语提取数据_导出.json"
        # 默认路径为当前运行目录
        default_path = os.path.join(os.getcwd(), default_filename)

        # 打开文件保存对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tra("导出术语"),
            default_path,
            "JSON Files (*.json)"
        )

        if not file_path:
            return  # 用户取消

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)

            self.success_toast(
                self.tra("导出成功"),
                self.tra("已成功导出 {} 条术语数据。").format(len(export_data))
            )
        except Exception as e:
            self.error_toast(self.tra("导出失败"), str(e))
            self.error(f"导出术语数据时发生错误: {e}")

    def _on_save_to_glossary(self, only_selected=False):
        """处理“保存到术语表”按钮点击事件"""
        if not self.extraction_results:
            self.warning_toast(self.tra("提示"), self.tra("没有可保存的术语。"))
            return
            
        target_results = []
        msg_prefix = ""
        
        # 检查是否只保存选中项
        # 如果是从按钮点击调用且有选中项，也可以认为是批量保存选中项的操作
        # 这里逻辑是：如果参数 only_selected=True，则只保存选中。
        # 如果按钮点击，检查是否有选中项。如果有选中项，询问用户或直接保存选中项？
        # 为了用户体验，我们改为：如果用户有选中行，则只保存选中行；如果没有选中，则保存所有。
        # 并通过 Toast 告知用户。
        
        selected_rows = self.table.selectionModel().selectedRows()
        
        if only_selected or selected_rows:
            # 获取选中行的 ID
            selected_ids = set()
            for index in selected_rows:
                term_item = self.table.item(index.row(), self.COL_TERM)
                if term_item:
                    selected_ids.add(term_item.data(Qt.UserRole))
            
            target_results = [r for r in self.extraction_results if r.get('_id') in selected_ids]
            msg_prefix = self.tra("选中")
            
            if not target_results:
                 self.warning_toast(self.tra("提示"), self.tra("未选中任何有效术语。"))
                 return
        else:
            # 保存所有
            target_results = self.extraction_results
            msg_prefix = self.tra("所有")

        try:
            config = self.load_config()
            prompt_dictionary_data = config.get("prompt_dictionary_data", [])
            existing_srcs = {item['src'] for item in prompt_dictionary_data}
            added_count = 0
            for result in target_results:
                src = result['term']
                if src not in existing_srcs:
                    new_entry = {
                        "src": src,
                        "dst": "",
                        "info": result['type']
                    }
                    prompt_dictionary_data.append(new_entry)
                    existing_srcs.add(src)
                    added_count += 1
            config["prompt_dictionary_data"] = prompt_dictionary_data
            self.save_config(config)
            
            if added_count == 0:
                 self.state_tooltip = self.success_toast(
                    self.tra("保存完成"),
                    self.tra(f"没有新的术语被添加（{msg_prefix}术语已存在）。")
                )
            else:
                self.success_toast(
                    self.tra("保存成功"),
                    self.tra(f"已添加 {added_count} 个新{msg_prefix}术语到术语表。")
                )
        except Exception as e:
            self.error_toast(self.tr("保存失败"), str(e))
            self.error(f"保存术语表时发生错误: {e}")
