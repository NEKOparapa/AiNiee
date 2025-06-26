import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidgetItem, 
                             QAbstractItemView, QHeaderView, QHBoxLayout, 
                             QSpacerItem, QSizePolicy)
from qfluentwidgets import TableWidget, PrimaryPushButton, FluentIcon
from Base.Base import Base

class TermResultPage(Base, QWidget):
    """
    用于显示术语提取结果的页面。
    """
    # 定义列索引常量
    COL_TERM = 0
    COL_TYPE = 1
    COL_CONTEXT = 2
    COL_FILE = 3

    def __init__(self, extraction_results: list, parent=None):
        super().__init__(parent)
        self.setObjectName('TermResultPage')
        
        # 存储提取结果以供后续使用
        self.extraction_results = extraction_results
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8) # 调整边距以容纳新控件
        self.layout.setSpacing(10) # 增加控件间距

        # 初始化顶部工具栏
        self._init_toolbar()

        self.table = TableWidget(self)
        self._init_table()
        self.layout.addWidget(self.table)
        
        # 使用传入的结果填充表格
        self._populate_data(extraction_results)

    def _init_toolbar(self):
        """初始化顶部工具栏"""
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加一个弹簧，将按钮推到右侧
        toolbar_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # 直接保存到术语表按钮
        self.save_button = PrimaryPushButton(FluentIcon.SAVE, self.tr("直接保存到术语表"), self)
        self.save_button.clicked.connect(self._on_save_to_glossary)
        toolbar_layout.addWidget(self.save_button)

        # 翻译后保存到术语表按钮
        self.translate_save_button = PrimaryPushButton(FluentIcon.EDIT, self.tr("翻译后保存到术语表"), self)
        self.translate_save_button.clicked.connect(self._on_translate_and_save)
        toolbar_layout.addWidget(self.translate_save_button)

        self.layout.addLayout(toolbar_layout)

    def _init_table(self):
        """初始化表格样式和表头"""
        self.headers = [self.tr("术语"), self.tr("类型"), self.tr("所在原文"), self.tr("来源文件")]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(self.COL_TERM, 180)
        self.table.setColumnWidth(self.COL_TYPE, 120)
        self.table.setColumnWidth(self.COL_CONTEXT, 400)
        self.table.setColumnWidth(self.COL_FILE, 180)

    def _populate_data(self, results: list):
        """用提取结果填充表格"""
        self.table.setRowCount(len(results))

        for row_idx, result in enumerate(results):
            term_item = QTableWidgetItem(result["term"])
            type_item = QTableWidgetItem(result["type"])
            context_item = QTableWidgetItem(result["context"])
            file_item = QTableWidgetItem(os.path.basename(result["file_path"]))

            self.table.setItem(row_idx, self.COL_TERM, term_item)
            self.table.setItem(row_idx, self.COL_TYPE, type_item)
            self.table.setItem(row_idx, self.COL_CONTEXT, context_item)
            self.table.setItem(row_idx, self.COL_FILE, file_item)
        
        self.table.resizeRowsToContents()

    def _on_save_to_glossary(self):
        """处理“直接保存到术语表”按钮点击事件"""
        if not self.extraction_results:
            self.warning_toast(self.tr("提示"), self.tr("没有可保存的术语。"))
            return

        try:
            config = self.load_config()
            prompt_dictionary_data = config.get("prompt_dictionary_data", [])
            
            # 使用集合快速查找已存在的 src
            existing_srcs = {item['src'] for item in prompt_dictionary_data}
            
            added_count = 0
            for result in self.extraction_results:
                src = result['term']
                # 如果术语表中不存在该原文，则添加
                if src not in existing_srcs:
                    new_entry = {
                        "src": src,
                        "dst": "",  # 译文留空
                        "info": result['type'] # 备注使用提取的类型
                    }
                    prompt_dictionary_data.append(new_entry)
                    existing_srcs.add(src) # 实时更新集合，处理提取结果中的重复项
                    added_count += 1
            
            config["prompt_dictionary_data"] = prompt_dictionary_data
            self.save_config(config)
            
            self.success_toast(
                self.tr("保存成功"),
                self.tr(f"已添加 {added_count} 个新术语到术语表。")
            )
        except Exception as e:
            self.error_toast(self.tr("保存失败"), str(e))
            self.error(f"保存术语表时发生错误: {e}")

    def _on_translate_and_save(self):
        """处理“翻译后保存到术语表”按钮点击事件"""
        if not self.extraction_results:
            self.warning_toast(self.tr("提示"), self.tr("没有可处理的术语。"))
            return

        # 直接发送完整的提取结果列表，包含术语和其上下文
        self.emit(Base.EVENT.TERM_TRANSLATE_SAVE_START, {
            "extraction_results": self.extraction_results
        })

        self.info_toast(
            self.tr("任务已开始"),
            self.tr("正在后台根据原文进行提取、翻译和保存，请稍后...")
        )