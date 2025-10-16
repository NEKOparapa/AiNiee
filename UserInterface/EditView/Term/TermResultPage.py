import os
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem,
                             QAbstractItemView, QHeaderView, QHBoxLayout,
                             QSpacerItem, QSizePolicy)

from qfluentwidgets import (TableWidget, PrimaryPushButton, FluentIcon,
                              RoundMenu, Action, MessageBox)
from Base.Base import Base

class TermResultPage(Base, QWidget):
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
        super().__init__(parent)
        self.setObjectName('TermResultPage')

        # 存储提取结果以供后续使用
        self.extraction_results = extraction_results

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
        self.translate_save_button = PrimaryPushButton(FluentIcon.LANGUAGE, self.tra("翻译后保存到术语表"), self)
        self.translate_save_button.clicked.connect(self._on_translate_and_save)
        toolbar_layout.addWidget(self.translate_save_button)
        self.save_button = PrimaryPushButton(FluentIcon.DICTIONARY_ADD, self.tra("直接保存到术语表"), self)
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
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

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
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        for row_idx, result in enumerate(results):
            term_item = QTableWidgetItem(result["term"])
            type_item = QTableWidgetItem(result["type"])
            context_item = QTableWidgetItem(result["context"])
            file_item = QTableWidgetItem(os.path.basename(result["file_path"]))
            count = result.get('count', 1)
            count_item = QTableWidgetItem()
            count_item.setData(Qt.DisplayRole, count)
            count_item.setData(Qt.EditRole, count)
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, self.COL_TERM, term_item)
            self.table.setItem(row_idx, self.COL_COUNT, count_item)
            self.table.setItem(row_idx, self.COL_TYPE, type_item)
            self.table.setItem(row_idx, self.COL_CONTEXT, context_item)
            self.table.setItem(row_idx, self.COL_FILE, file_item)
        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(self.COL_COUNT, Qt.DescendingOrder)


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

        # 获取所有不重复的选中行号
        rows_to_delete = sorted(list(set(index.row() for index in selected_indexes)))

        # 弹出确认对话框
        confirm_msg = MessageBox(
            self.tra("确认删除"),
            self.tra("您确定要删除选中的 {} 行吗？此操作不可撤销。").format(len(rows_to_delete)),
            self.window()
        )
        if not confirm_msg.exec():
            return # 用户点击了取消

        # 从后往前删除，避免索引变化导致错误
        for row in reversed(rows_to_delete):
            # 从数据模型中删除
            del self.extraction_results[row]
            # 从视图（表格）中删除
            self.table.removeRow(row)

        self.success_toast(
            self.tra("操作成功"),
            self.tra("已成功删除 {} 行。").format(len(rows_to_delete))
        )

    def _on_save_to_glossary(self):
        """处理“直接保存到术语表”按钮点击事件"""
        if not self.extraction_results:
            self.warning_toast(self.tra("提示"), self.tra("没有可保存的术语。"))
            return
        try:
            config = self.load_config()
            prompt_dictionary_data = config.get("prompt_dictionary_data", [])
            existing_srcs = {item['src'] for item in prompt_dictionary_data}
            added_count = 0
            for result in self.extraction_results:
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
            self.success_toast(
                self.tra("保存成功"),
                self.tra(f"已添加 {added_count} 个新术语到术语表。")
            )
        except Exception as e:
            self.error_toast(self.tr("保存失败"), str(e))
            self.error(f"保存术语表时发生错误: {e}")

    def _on_translate_and_save(self):
        """处理“翻译后保存到术语表”按钮点击事件"""
        if not self.extraction_results:
            self.warning_toast(self.tra("提示"), self.tra("没有可处理的术语。"))
            return
        self.emit(Base.EVENT.TERM_TRANSLATE_SAVE_START, {
            "extraction_results": self.extraction_results
        })
        self.info_toast(
            self.tra("任务已开始"),
            self.tra("正在后台根据原文进行提取、翻译和保存，请稍后...")
        )