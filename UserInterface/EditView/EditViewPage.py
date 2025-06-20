import json
import os
import threading
import time
from PyQt5.QtCore import QPoint, QVariant, Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import (QAbstractItemView, QFrame, QHeaderView, QScrollArea, QTableWidgetItem, QTreeWidgetItem,
                             QWidget, QHBoxLayout, QVBoxLayout, 
                             QSplitter, QStackedWidget)
from qfluentwidgets import (Action, BodyLabel,  CaptionLabel, MessageBox, PrimarySplitPushButton, PushButton, RoundMenu, TitleLabel,  ToggleToolButton, TransparentPushButton, TransparentToolButton,
                            TreeWidget, TabBar, FluentIcon as FIF, CardWidget, Action, RoundMenu, TableWidget,
                            ProgressBar)

from Base.Base import Base

from UserInterface.EditView.MonitoringPage import MonitoringPage
from UserInterface.EditView.StartupPage import StartupPage
from ModuleFolders.TaskConfig.TaskType import TaskType

# 底部命令栏
class BottomCommandBar(Base,CardWidget):
    arrowClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 5, 8, 5)
        self.layout.setSpacing(12)

        # 初始化当前模式
        self.current_mode = TaskType.TRANSLATION  # 默认模式为翻译

        self.back_btn = PushButton(FIF.RETURN, "返回")
        self.back_btn.setIconSize(QSize(16, 16))
        self.back_btn.setFixedHeight(32)

        project_widget = QWidget()
        project_layout = QVBoxLayout(project_widget)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.project_name = CaptionLabel('项目名字')
        self.project_name.setFixedWidth(200)
        self.progress_status = CaptionLabel("0/0")
        top_row.addWidget(self.project_name, alignment=Qt.AlignLeft)
        top_row.addStretch()
        top_row.addWidget(self.progress_status, alignment=Qt.AlignRight)

        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(45)
        self.progress_bar.setMinimumWidth(400)

        project_layout.addStretch(1)
        project_layout.addLayout(top_row)
        project_layout.addWidget(self.progress_bar)
        project_layout.addStretch(1)

        # 创建翻译和润色的下拉菜单
        self.menu = RoundMenu(parent=self)
        self.translate_action = Action(FIF.PLAY, '开始翻译')
        self.polish_action = Action(FIF.ALBUM, '开始润色')
        self.menu.addAction(self.translate_action)
        self.menu.addAction(self.polish_action)

        # 初始按钮
        self.start_btn = PrimarySplitPushButton(FIF.PLAY, '开始翻译')
        self.start_btn.setFlyout(self.menu)
        self.continue_btn = TransparentPushButton(FIF.ROTATE, '继续')
        self.continue_btn.setEnabled(False)  # 初始不可用
        self.stop_btn = TransparentPushButton(FIF.CANCEL_MEDIUM, '停止')
        self.schedule_btn = TransparentPushButton(FIF.DATE_TIME, '定时')
        self.export_btn = TransparentPushButton(FIF.SHARE, "导出")
        self.arrow_btn = ToggleToolButton()
        self.arrow_btn.setIcon(FIF.UP)
        self.arrow_btn.setIconSize(QSize(16, 16))
        self.arrow_btn.setFixedHeight(32)

        for btn in [self.start_btn, self.continue_btn, self.arrow_btn]:
            btn.setIconSize(QSize(16, 16))
            btn.setFixedHeight(32)

        self.layout.addWidget(self.back_btn)
        self.layout.addStretch(1)
        self.layout.addWidget(project_widget)
        self.layout.addStretch(1)
        self.layout.addWidget(self.start_btn)
        self.layout.addWidget(self.continue_btn)
        self.layout.addWidget(self.stop_btn)
        self.layout.addWidget(self.schedule_btn)
        self.layout.addWidget(self.export_btn)
        self.layout.addWidget(self.arrow_btn)

        self.arrow_btn.clicked.connect(self.on_arrow_clicked)

        # 注册事件
        self.subscribe(Base.EVENT.TASK_STOP_DONE, self.translation_stop_done)

        # 连接按钮
        self.start_btn.clicked.connect(self.command_play)
        self.stop_btn.clicked.connect(self.command_stop)
        self.continue_btn.clicked.connect(self.command_continue)
        self.export_btn.clicked.connect(self.command_export)

        # 连接菜单项的点击事件
        self.translate_action.triggered.connect(
            lambda: self._on_mode_selected(TaskType.TRANSLATION, self.translate_action)
        )
        self.polish_action.triggered.connect(
            lambda: self._on_mode_selected(TaskType.POLISH, self.polish_action)
        )

        # 注册事件
        self.subscribe(Base.EVENT.TASK_UPDATE, self.data_update) # 监听监控数据更新事件


    # 处理模式选择的函数
    def _on_mode_selected(self, mode: str, action: Action):
        self.current_mode = mode
        self.start_btn.setText(action.text())
        print(f"模式已切换为: {self.current_mode}")

    # 导出已完成的内容
    def command_export(self) -> None:
        self.emit(Base.EVENT.TASK_MANUAL_EXPORT, {})
        info_cont = self.tra("已根据当前的翻译数据在输出文件夹下生成翻译文件") + "  ... "
        self.info_toast("Info", info_cont)

    # 启用关闭继续翻译按钮
    def enable_continue_button(self, enable: bool) -> None:
        self.continue_btn.setEnabled(enable)

    # 监控页面展开信号
    def on_arrow_clicked(self):
        self.arrowClicked.emit()

    # 底部进度条更新事件
    def data_update(self, event: int, data: dict) -> None:
        # 检查是否包含进度信息
        if data.get("line") is not None and data.get("total_line") is not None:
            line = data.get("line")
            total_line = data.get("total_line")

            # 更新进度文本标签 (例如 "15/100")
            self.progress_status.setText(f"{line}/{total_line}")

            # 更新进度条
            if total_line > 0:
                percentage = int((line / total_line) * 100)
                self.progress_bar.setValue(percentage)

            else:
                # 如果总行数为0，则将进度条重置为0
                self.progress_bar.setValue(0)

    # 开始
    def command_play(self) -> None:
        if self.continue_btn.isEnabled():
            info_cont1 = self.tra("将重置尚未完成的翻译任务，是否确认开始新的翻译任务") + "  ... ？"
            message_box = MessageBox("Warning", info_cont1, self.window())
            info_cont2 = self.tra("确认")
            message_box.yesButton.setText(info_cont2)
            info_cont3 = self.tra("取消")
            message_box.cancelButton.setText(info_cont3)
            if not message_box.exec():
                return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.continue_btn.setEnabled(False)

        # 触发翻译开始事件
        self.emit(Base.EVENT.TASK_START, {
            "continue_status": False,
            "current_mode": self.current_mode  # 发送当前选择的模式
        })

        # 自动展开监控页面
        if not self.arrow_btn.isChecked():
            self.arrow_btn.setChecked(True)
            self.arrowClicked.emit()

    # 停止
    def command_stop(self) -> None:
        info_cont1 = self.tra("是否确定停止任务") + "  ... ？"
        message_box = MessageBox("Warning", info_cont1, self.window())
        info_cont2 = self.tra("确认")
        message_box.yesButton.setText(info_cont2)
        info_cont3 = self.tra("取消")
        message_box.cancelButton.setText(info_cont3)

        if message_box.exec():
            info_cont4 = self.tra("正在停止翻译任务") + "  ... "
            print(info_cont4)
            self.stop_btn.setEnabled(False)
            self.emit(Base.EVENT.TASK_STOP, {})

    # 继续翻译
    def command_continue(self) -> None:
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        print(f"模式: {self.current_mode}")
        self.emit(Base.EVENT.TASK_START, {
            "continue_status": True,
            "current_mode": self.current_mode # 发送当前选择的模式
        })

    # 翻译停止完成事件
    def translation_stop_done(self, event: int, data: dict) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        Base.work_status = Base.STATUS.IDLE
        self.emit(Base.EVENT.TASK_CONTINUE_CHECK, {})

# 层级浏览器
class NavigationCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)
        
        self.toolbar = QWidget()
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_layout.setSpacing(8)
        
        self.search_button = TransparentToolButton(FIF.SEARCH)
        self.toolbar_layout.addStretch(1)  
        self.toolbar_layout.addWidget(self.search_button)
        self.toolbar_layout.addStretch(1)  
        self.layout.addWidget(self.toolbar)
        
        self.tree = TreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.layout.addWidget(self.tree)

    def update_tree(self, hierarchy: dict):
        """
        根据提供的文件层级字典更新树状视图
        """
        self.tree.clear()
        
        if not hierarchy:
            return

        # 存储文件夹的QTreeWidgetItem，以便添加文件
        folder_items = {}

        # 先创建所有文件夹项
        sorted_dirs = sorted(hierarchy.keys())
        for dir_path in sorted_dirs:
            if dir_path == '.': # 根目录
                parent_item = self.tree.invisibleRootItem()
            else:
                # 逐级创建父目录
                parts = dir_path.replace('\\', '/').split('/')
                current_path = ""
                parent_item = self.tree.invisibleRootItem()
                for part in parts:
                    if not current_path:
                        current_path = part
                    else:
                        current_path = f"{current_path}/{part}"
                    
                    if current_path not in folder_items:
                        new_folder_item = QTreeWidgetItem([part])
                        # 标记为文件夹，不存储路径
                        new_folder_item.setData(0, Qt.UserRole, None) 
                        parent_item.addChild(new_folder_item)
                        folder_items[current_path] = new_folder_item
                        parent_item = new_folder_item
                    else:
                        parent_item = folder_items[current_path]
            
            # 添加文件到对应的文件夹项
            for filename in hierarchy[dir_path]:
                # 完整的相对路径
                full_path = os.path.join(dir_path, filename) if dir_path != '.' else filename
                file_item = QTreeWidgetItem([filename])
                # 使用 setData 存储文件的完整相对路径
                file_item.setData(0, Qt.UserRole, QVariant(full_path)) 
                parent_item.addChild(file_item)

        self.tree.expandAll()

# 标签栏
class PageCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        # 无边框

        # 创建水平布局用于放置 TabBar 和按钮
        tab_layout = QHBoxLayout()

        # 创建并配置 TabBar
        self.tab_bar = TabBar(self)
        self.tab_bar.setTabMaximumWidth(160)
        self.tab_bar.setTabShadowEnabled(False)
        self.tab_bar.setTabSelectedBackgroundColor(Qt.white, Qt.lightGray)
        self.tab_bar.setScrollable(True)

        # 创建按钮容器
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)

        # 创建视图切换按钮
        self.view_button = TransparentToolButton(FIF.VIEW)
        self.view_button.setIconSize(QSize(16, 16))
        self.view_button.clicked.connect(self.on_view_button_clicked)

        # 将按钮添加到按钮容器布局
        button_layout.addWidget(self.view_button)


        # 将 TabBar 和按钮容器添加到水平布局
        tab_layout.addWidget(self.tab_bar, 1)  # 参数 1 表示该控件是可拉伸的
        tab_layout.addWidget(button_container) # 参数 0 (默认) 表示该控件不拉伸，保持原始大小

        # 将水平布局添加到主布局
        self.layout.addLayout(tab_layout)

        # 创建并添加 QStackedWidget
        self.stacked_widget = QStackedWidget(self)
        self.layout.addWidget(self.stacked_widget)

    def on_view_button_clicked(self):
        """
        提取当前前台标签页的所有文本，生成新的视图标签页进行美观展示。
        """
        current_index = self.stacked_widget.currentIndex()

        # 处理没有标签页的情况
        if current_index == -1:
            MessageBox("提示", "当前没有打开的标签页。", self.window()).exec()
            return

        # 获取当前标签页和其数据表格
        current_tab = self.stacked_widget.widget(current_index)

        # 检查当前是否为原始数据表格页，而不是一个视图页
        if not isinstance(current_tab, TabInterface):
            MessageBox("提示", "请在原始数据表格标签页上执行此操作。", self.window()).exec()
            return

        table_page = current_tab.tableView
        table = table_page.table

        # 提取所有文本
        all_text_data = []
        for row in range(table.rowCount()):
            row_num_item = table.item(row, BasicTablePage.COL_NUM)
            source_item = table.item(row, BasicTablePage.COL_SOURCE)
            trans_item = table.item(row, BasicTablePage.COL_TRANS)
            polish_item = table.item(row, BasicTablePage.COL_POLISH)

            all_text_data.append({
                "row": row_num_item.text() if row_num_item else str(row + 1),
                "source": source_item.text() if source_item else "",
                "translation": trans_item.text() if trans_item else "",
                "polish": polish_item.text() if polish_item else ""
            })

        # 生成新的视图标签页
        original_tab_name = self.tab_bar.tabText(current_index)

        view_tab_name = f"视图 - {original_tab_name}"
        # 使用时间戳确保路由键的唯一性
        view_route_key = f"view_{int(time.time())}"

        # 检查是否已存在此文件的视图页，避免重复创建
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabText(i) == view_tab_name:
                self.tab_bar.setCurrentIndex(i) # 如果存在，直接切换过去
                return

        # 创建新的视图页面实例
        new_view_page = TextViewPage(all_text_data)
        new_view_page.setObjectName(view_route_key) # 设置对象名以便追踪

        # 添加新标签页并自动跳转
        self.stacked_widget.addWidget(new_view_page)
        self.tab_bar.addTab(routeKey=view_route_key, text=view_tab_name)

        new_index = self.tab_bar.count() - 1
        self.tab_bar.setCurrentIndex(new_index)
        self.stacked_widget.setCurrentIndex(new_index)

# 文本视图页
class TextViewPage(QWidget):
    def __init__(self, text_data: list, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("TextViewPage")

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # 滚动区域，以便内容超出时可以滚动
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        # 滚动区域内的内容小部件
        self.scroll_content_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content_widget)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(10)

        self._populate_data(text_data)

        self.scroll_area.setWidget(self.scroll_content_widget)
        self.main_layout.addWidget(self.scroll_area)

    def _populate_data(self, text_data: list):
        """用传入的文本数据填充视图"""
        if not text_data:
            self.scroll_layout.addWidget(BodyLabel("没有可供预览的文本。", self))
            return

        for i, row_data in enumerate(text_data):
            # 为每一行数据创建一个卡片
            card = CardWidget(self)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(8)
            card_layout.setContentsMargins(15, 10, 15, 10)

            # 将原文作为标题
            source_title = TitleLabel(f"原文 (第 {row_data['row']} 行)", self)
            card_layout.addWidget(source_title)

            source_content = BodyLabel(row_data['source'], self)
            source_content.setWordWrap(True)
            card_layout.addWidget(source_content)

            card_layout.addSpacing(10)

            # 添加译文（如果存在）
            if row_data['translation']:
                trans_title = BodyLabel("译文:", self)
                card_layout.addWidget(trans_title)
                trans_content = BodyLabel(row_data['translation'], self)
                trans_content.setWordWrap(True)
                card_layout.addWidget(trans_content)
                card_layout.addSpacing(5)

            # 添加润文（如果存在）
            if row_data['polish']:
                polish_title = BodyLabel("润文:", self)
                card_layout.addWidget(polish_title)
                polish_content = BodyLabel(row_data['polish'], self)
                polish_content.setWordWrap(True)
                card_layout.addWidget(polish_content)

            self.scroll_layout.addWidget(card)

        # 在末尾添加一个伸展项，将所有卡片推向顶部
        self.scroll_layout.addStretch(1)

# 标签页基类
class TabInterface(QWidget):
    def __init__(self, text: str, file_path: str, file_items: list, cache_manager, parent=None):
        super().__init__(parent=parent)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        
        # 将参数传递给 BasicTablePage
        self.tableView = BasicTablePage(file_path, file_items, cache_manager, self)
        self.vBoxLayout.addWidget(self.tableView)
        
        # 使用文件路径作为唯一的对象名称，避免特殊字符问题
        self.setObjectName(file_path)

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

        self.headers = ["行", "原文", "译文", "润文"]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 55)
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

            # 原文列 (不可编辑)
            source_item = QTableWidgetItem(item_data.source_text)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 1, source_item)
            
            # 译文、润文列 (可编辑)
            self.table.setItem(row_idx, 2, QTableWidgetItem(item_data.translated_text))
            self.table.setItem(row_idx, 3, QTableWidgetItem(item_data.polished_text or '')) # 确保 None 显示为空字符串
        
        self.table.resizeRowsToContents()

        # 恢复信号
        self.table.blockSignals(False)

    # 监听用户编辑单元格
    def _on_item_changed(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()

        # 只处理 "译文" 和 "润文" 列的修改
        if col not in [self.COL_TRANS, self.COL_POLISH]:
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
            menu.addAction(Action(FIF.EDIT, "翻译文本", triggered=self._translate_text))
            menu.addAction(Action(FIF.BRUSH, "润色文本", triggered=self._polish_text))
            menu.addAction(Action(FIF.BRUSH, "排序文本", triggered=self._format_text))
            menu.addSeparator()

            ### 新增/修改开始 ###
            # 添加“原文复制到译文”和“清空”等手动编辑操作
            menu.addAction(Action(FIF.COPY, "禁止翻译", triggered=self._copy_source_to_translation))
            menu.addAction(Action(FIF.DELETE, "清空翻译", triggered=self._clear_translation))
            menu.addAction(Action(FIF.DELETE, "清空润色", triggered=self._clear_polishing))
            menu.addSeparator()
            ### 新增/修改结束 ###

        # “行数”选项总是显示
        row_count = self.table.rowCount()
        row_count_action = Action(FIF.LEAF, f"行数: {row_count}")
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
        
        self.table.resizeRowsToContents()
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
        self.info_toast("排版完成", f"表格已成功更新，行数变化: {row_count_change:+}")



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
        self.info_toast("提示", f"已提交 {len(items_to_translate)} 行文本的翻译任务。")

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
        self.info_toast("提示", f"已提交 {len(items_to_polish)} 行文本的润色任务。")

    # 排版文本
    def _format_text(self):
        """处理右键菜单的“排版文本”操作"""
        selected_rows = self._get_selected_rows_indices()
        if not selected_rows:
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
        self.info_toast("提示", f"已提交 {len(items_to_format)} 行文本的排版任务。")

    ### 新增开始 ###
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
        
        self.info_toast("操作完成", f"已将 {len(selected_rows)} 行的原文复制到译文。")
    ### 新增结束 ###

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

# 主界面
class EditViewPage(Base,QFrame):

    def __init__(self, text: str, window, plugin_manager, cache_manager, file_reader) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.cache_manager = cache_manager  # 缓存管理器
        self.file_reader = file_reader  # 文件读取器

        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 四周边距归零
        main_layout.setSpacing(0)  # 控件间距归零

        # 顶级堆叠控件，用于切换启动页和主界面
        self.top_stacked_widget = QStackedWidget()
        main_layout.addWidget(self.top_stacked_widget)

        # 创建启动页面
        support_project_types = self.file_reader.get_support_project_types()  # 获取支持的项目类型
        self.startup_page = StartupPage(support_project_types,window,cache_manager, file_reader)

        # 创建主界面控件
        self.main_interface = QWidget()
        self.main_interface_layout = QVBoxLayout(self.main_interface)
        self.main_interface_layout.setContentsMargins(0, 0, 0, 0)  # 四周边距归零
        self.main_interface_layout.setSpacing(0)  # 控件间距归零

        # 向主界面添加堆叠控件
        self.stacked_widget = QStackedWidget()

        # 主页面设置
        self.main_page = QWidget()
        self.main_page_layout = QVBoxLayout(self.main_page)
        self.splitter = QSplitter(Qt.Horizontal)  # 水平分割器
        self.nav_card = NavigationCard()  # 导航卡片
        self.page_card = PageCard()  # 页面卡片
        self.splitter.addWidget(self.nav_card)
        self.splitter.addWidget(self.page_card)
        self.splitter.setSizes([200, 800])  # 设置左右区域初始宽度
        self.main_page_layout.addWidget(self.splitter)

        # 监控页面设置
        self.monitoring_page = MonitoringPage()

        # 向堆叠控件添加页面，即信息展示页面与监控页面
        self.stacked_widget.addWidget(self.main_page)
        self.stacked_widget.addWidget(self.monitoring_page)

        # 底部命令栏设置
        self.bottom_bar_main = BottomCommandBar()

        # 组装主界面
        self.main_interface_layout.addWidget(self.stacked_widget)
        self.main_interface_layout.addWidget(self.bottom_bar_main)

        # 向顶级堆叠控件添加启动页面与主页面
        self.top_stacked_widget.addWidget(self.startup_page)
        self.top_stacked_widget.addWidget(self.main_interface)

        # 设置初始页面
        #self.stacked_widget.setCurrentIndex(1)  # 默认显示启动页
        self.top_stacked_widget.setCurrentIndex(0)  # 默认显示启动页

        # 连接各种信号
        self.startup_page.folderSelected.connect(self.on_folder_selected) # 连接信号到界面切换和路径处理
        self.bottom_bar_main.back_btn.clicked.connect(self.on_back_button_clicked)  # 返回按钮绑定
        self.nav_card.tree.itemClicked.connect(self.on_tree_item_clicked)  # 树形项点击事件
        self.page_card.tab_bar.currentChanged.connect(self.on_tab_changed)  # 标签页切换事件
        self.page_card.tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)  # 标签页关闭请求
        self.bottom_bar_main.arrowClicked.connect(self.toggle_page)  # 箭头按钮点击切换页面

    # 页面显示事件
    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 触发继续状态检测事件
        self.translation_continue_check()

    # 继续翻译状态检查事件
    def translation_continue_check(self) -> None:
        threading.Thread(target = self.translation_continue_check_target, daemon=True).start()

    # 继续翻译状态检查
    def translation_continue_check_target(self) -> None:
        time.sleep(0.5) # 等待页面切换效果

        self.continue_status = False # 默认为False

        if Base.work_status == Base.STATUS.IDLE:
            config = self.load_config()
            cache_folder_path = os.path.join(config.get("label_output_path", "./output"), "cache") # 添加默认值

            if not os.path.isdir(cache_folder_path):
                return False

            json_file_path = os.path.join(cache_folder_path, "ProjectStatistics.json")
            if not os.path.isfile(json_file_path):
                return False

            # 获取小文件
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            total_line = data["total_line"] # 获取需翻译行数
            line = data["line"] # 获取已翻译行数

            if total_line == line:
                self.continue_status = False
            else:
                self.continue_status = True

        # 根据翻译状态，更新界面
        if self.continue_status == True :
            # 启动页显示继续翻译按钮
            self.startup_page.show_continue_button(True)
            # 启用底部命令栏的继续按钮
            self.bottom_bar_main.enable_continue_button(True)
            #self.top_stacked_widget.setCurrentIndex(1) # 切换到主界面

        else:
            self.startup_page.show_continue_button(False)
            self.bottom_bar_main.enable_continue_button(False)

    # 输入文件夹路径改变信号
    def on_folder_selected(self, mode: str):
        # 从缓存器获取文件层级结构
        file_hierarchy = self.cache_manager.get_file_hierarchy()
        # 更新导航卡片的树状视图
        self.nav_card.update_tree(file_hierarchy)

        # 切换到主界面
        self.top_stacked_widget.setCurrentWidget(self.main_interface)

    # 底部命令栏返回按钮事件
    def on_back_button_clicked(self):

        if Base.work_status == Base.STATUS.IDLE:
            # 如果当前工作状态为空闲，则直接切换到启动页面
            self.top_stacked_widget.setCurrentIndex(0)
            return
        
    # 展开按钮事件，展开或收起监控页面
    def toggle_page(self):
        current_index = self.stacked_widget.currentIndex()
        new_index = 1 - current_index
        self.stacked_widget.setCurrentIndex(new_index)

    # 层级浏览器点击事件
    def on_tree_item_clicked(self, item, column):
        
        # 从 QTreeWidgetItem 中获取之前存储的文件路径
        file_path_variant = item.data(0, Qt.UserRole)
        
        # 如果 data 为 None，说明点击的是文件夹，直接返回
        if not file_path_variant:
            return

        file_path = file_path_variant # QVariant 会自动转换为 Python 类型

        # 检查标签页是否已经存在
        for i in range(self.page_card.stacked_widget.count()):
                widget = self.page_card.stacked_widget.widget(i)
                # 检查 widget 是否存在且 objectName 是否匹配
                if widget and widget.objectName() == file_path:
                    # 如果找到了，说明标签页已存在。
                    self.page_card.tab_bar.setCurrentIndex(i)
                    self.page_card.stacked_widget.setCurrentIndex(i)
                    return  # 任务完成，退出函数

        # 从缓存中获取该文件的所有文本项
        cache_file = self.cache_manager.project.get_file(file_path)
        if not cache_file:
            MessageBox("错误", f"无法从缓存中加载文件: {file_path}", self).exec()
            return
        
        file_items = cache_file.items

        # 创建新标签页，并传递所需的所有信息
        tab_name = os.path.basename(file_path) # 标签页只显示文件名
        new_tab = TabInterface(tab_name, file_path, file_items, self.cache_manager)
        
        self.page_card.stacked_widget.addWidget(new_tab)

        # 使用唯一的 file_path 作为 routeKey
        # 使用tab_name 作为显示的文本
        self.page_card.tab_bar.addTab(file_path, tab_name)
        
        new_index = self.page_card.tab_bar.count() - 1
        self.page_card.tab_bar.setCurrentIndex(new_index)

        # 立即切换到新创建的页面
        self.page_card.stacked_widget.setCurrentWidget(new_tab)

    # 标签页点击事件，切换到对应的页面
    def on_tab_changed(self, index):
        if index >= 0:
            widget = self.page_card.stacked_widget.widget(index)
            if widget:
                self.page_card.stacked_widget.setCurrentWidget(widget)

    # 标签页删除事件
    def on_tab_close_requested(self, index):
        # 确保 widget 存在再移除
        widget_to_remove = self.page_card.stacked_widget.widget(index)
        if widget_to_remove:
            self.page_card.stacked_widget.removeWidget(widget_to_remove)
            # Qt 会在稍后安全地删除 widget
            widget_to_remove.deleteLater()
        
        self.page_card.tab_bar.removeTab(index)