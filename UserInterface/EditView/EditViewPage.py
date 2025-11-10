import json
import os
import threading
import time
from PyQt5.QtCore import QTime, QVariant, Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import ( QFileDialog, QFrame, QTreeWidgetItem,
                             QWidget, QHBoxLayout, QVBoxLayout, 
                             QSplitter, QStackedWidget, QGridLayout)
from qfluentwidgets import (Action,  CaptionLabel, MessageBox, PrimarySplitPushButton, PushButton, RoundMenu,  ToggleToolButton, TransparentPushButton, TransparentToolButton,
                            TreeWidget, TabBar, FluentIcon as FIF, CardWidget, Action, RoundMenu, ProgressBar)
from qframelesswindow import QTimer

from Base.Base import Base
from ModuleFolders.ResponseChecker.TranslationChecker import TranslationChecker, CheckResult
from UserInterface.EditView.Monitoring.MonitoringPage import MonitoringPage
from UserInterface.EditView.Startup.StartupPage import StartupPage
from ModuleFolders.TaskConfig.TaskType import TaskType
from UserInterface.EditView.Check.LanguageCheckDialog import LanguageCheckDialog
from UserInterface.EditView.Search.SearchDialog import SearchDialog
from UserInterface.EditView.Search.SearchResultPage import SearchResultPage
from UserInterface.EditView.Timer.ScheduledDialogPage import ScheduledDialogPage
from UserInterface.EditView.TextViewPage import TextViewPage
from UserInterface.EditView.BasicTablePage import BasicTablePage
from UserInterface.EditView.Term.TermResultPage import TermResultPage
from UserInterface.EditView.Term.TermExtractionDialog import TermExtractionDialog

# 底部命令栏
class BottomCommandBar(Base,CardWidget):
    arrowClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 5, 8, 5)
        self.layout.setSpacing(12)

        # 初始化
        self.current_mode = TaskType.TRANSLATION
        self.scheduled_timer = None # 用于一次性定时任务
        self.ui_update_timer = QTimer(self) # 用于任务进行中持续刷新UI
        self.ui_update_timer.setInterval(1000) # 每秒触发一次
        # 定时器刷新事件
        self.ui_update_timer.timeout.connect(lambda: self.emit(Base.EVENT.TASK_UPDATE, {}))

        self.back_btn = PushButton(FIF.RETURN, self.tra('返回'))
        self.back_btn.setIconSize(QSize(16, 16))
        self.back_btn.setFixedHeight(32)

        project_widget = QWidget()
        project_layout = QVBoxLayout(project_widget)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.project_name = CaptionLabel('project_name')
        self.project_name.setFixedWidth(200)
        self.progress_status = CaptionLabel("NA")
        top_row.addWidget(self.project_name, alignment=Qt.AlignLeft)
        top_row.addStretch()
        top_row.addWidget(self.progress_status, alignment=Qt.AlignRight)

        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumWidth(400)

        project_layout.addStretch(1)
        project_layout.addLayout(top_row)
        project_layout.addWidget(self.progress_bar)
        project_layout.addStretch(1)

        # 创建翻译和润色的下拉菜单
        self.menu = RoundMenu(parent=self)
        self.translate_action = Action(FIF.PLAY, self.tra('开始翻译'))
        self.polish_action = Action(FIF.ALBUM, self.tra('开始润色'))
        self.menu.addAction(self.translate_action)
        self.menu.addAction(self.polish_action)

        # 初始按钮
        self.start_btn = PrimarySplitPushButton(FIF.PLAY, self.tra('开始翻译'))
        self.start_btn.setFlyout(self.menu)
        self.continue_btn = TransparentPushButton(FIF.ROTATE, self.tra('继续'))
        self.continue_btn.setEnabled(False)  # 初始不可用
        self.stop_btn = TransparentPushButton(FIF.CANCEL_MEDIUM, self.tra('停止'))
        self.stop_btn.setEnabled(False)  # 初始不可用
        self.schedule_btn = TransparentPushButton(FIF.DATE_TIME, self.tra('定时'))
        self.export_btn = TransparentPushButton(FIF.SHARE, self.tra("导出"))
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

        # 连接按钮
        self.start_btn.clicked.connect(self.command_play)
        self.stop_btn.clicked.connect(self.command_stop)
        self.continue_btn.clicked.connect(self.command_continue)
        self.export_btn.clicked.connect(self.command_export)
        self.schedule_btn.clicked.connect(self.command_schedule) 
        self.arrow_btn.clicked.connect(self.on_arrow_clicked)

        # 连接菜单项的点击事件
        self.translate_action.triggered.connect(
            lambda: self._on_mode_selected(TaskType.TRANSLATION, self.translate_action)
        )
        self.polish_action.triggered.connect(
            lambda: self._on_mode_selected(TaskType.POLISH, self.polish_action)
        )

        # 订阅事件
        self.subscribe(Base.EVENT.TASK_UPDATE, self.data_update)
        self.subscribe(Base.EVENT.TASK_STOP_DONE, self.task_stop_done)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)

    # 更新项目名称标签的方法
    def update_project_name(self, name: str):
        self.project_name.setText(name)

    # 任务模式切换
    def _on_mode_selected(self, mode: str, action: Action):
        self.current_mode = mode
        self.start_btn.setText(action.text())
        if self.current_mode == TaskType.TRANSLATION:
            info_cont = ": " + self.tra("翻译模式")
            self.info_toast(self.tra("模式已切换为"), info_cont)
        elif self.current_mode == TaskType.POLISH:
            info_cont = ": " + self.tra("润色模式")
            self.info_toast(self.tra("模式已切换为"), info_cont)

    # 继续按钮的显示隐藏
    def enable_continue_button(self, enable: bool) -> None:
        self.continue_btn.setEnabled(enable)

    # 应用关闭事件
    def app_shut_down(self, event: int, data: dict) -> None:
        # 确保应用关闭时所有定时器都停止
        if self.scheduled_timer:
            self.scheduled_timer.stop()
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()

    # 任务停止完成事件
    def task_stop_done(self, event: int, data: dict) -> None:
        """任务停止完成事件处理"""
        # 关闭UI刷新器
        if self.ui_update_timer.isActive():
            self.ui_update_timer.stop()

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        Base.work_status = Base.STATUS.IDLE
        self.emit(Base.EVENT.TASK_CONTINUE_CHECK, {})

    # 更新底部进度条
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
    # 开始按钮
    def command_play(self) -> None:
        """开始新任务"""
        self.cancel_scheduled_task() # 如果有定时任务，先取消

        if self.continue_btn.isEnabled():
            info_cont1 = self.tra("将重置尚未完成的任务") + "  ... ？"
            message_box = MessageBox("Warning", info_cont1, self.window())
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))
            if not message_box.exec():
                return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.continue_btn.setEnabled(False)
        
        self.emit(Base.EVENT.TASK_START, {
            "continue_status": False,
            "current_mode": self.current_mode
        })
        
        # 开启UI刷新器
        self.ui_update_timer.start()

        if not self.arrow_btn.isChecked():
            self.arrow_btn.setChecked(True)
            self.arrowClicked.emit()

    # 停止按钮
    def command_stop(self) -> None:
        """停止当前任务"""
        self.cancel_scheduled_task() # 如果有定时任务，也一并取消

        info_cont1 = self.tra("是否确定停止任务") + "  ... ？"
        message_box = MessageBox("Warning", info_cont1, self.window())
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))

        if message_box.exec():
            self.info("正在停止任务 ... ")
            self.emit(Base.EVENT.TASK_STOP, {})

    # 继续按钮
    def command_continue(self) -> None:
        """继续未完成的任务"""
        self.cancel_scheduled_task() # 如果有定时任务，先取消

        self.start_btn.setEnabled(False)
        self.continue_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        self.emit(Base.EVENT.TASK_START, {
            "continue_status": True,
            "current_mode": self.current_mode
        })
        
        # 开启UI刷新器
        self.ui_update_timer.start()

    # 导出按钮
    def command_export(self) -> None:
        selected_path = QFileDialog.getExistingDirectory(
            self.window(), self.tra("选择导出目录"), "."
        )
        if selected_path:
            self.emit(Base.EVENT.TASK_MANUAL_EXPORT, {"export_path": selected_path})

    # 展开按钮
    def on_arrow_clicked(self):
        self.arrowClicked.emit()

    # 定时按钮
    def command_schedule(self) -> None:
        """处理定时按钮点击事件"""
        # 如果已经有定时任务，则取消
        if self.scheduled_timer:
            self.cancel_scheduled_task()
            info_cont = self.tra("定时任务已取消") + "  ... "
            self.info_toast("", info_cont)
            return

        # 创建定时对话框
        dialog = ScheduledDialogPage(parent=self.window(), title=self.tra("定时任务"))
        if dialog.exec_():
            scheduled_time = dialog.get_scheduled_time()
            current_time = QTime.currentTime()

            current_msecs = current_time.msecsSinceStartOfDay()
            scheduled_msecs = scheduled_time.msecsSinceStartOfDay()

            msec_diff = scheduled_msecs - current_msecs
            # 如果设定时间早于当前时间，则认为是明天
            if msec_diff < 0:
                msec_diff += 24 * 60 * 60 * 1000

            # 检查时间间隔是否有效（例如，至少5秒）
            if msec_diff < 5000:
                warning_box = MessageBox(self.tra("无效时间"), self.tra("与当前时间间隔过短"), self.window())
                warning_box.yesButton.setText(self.tra("确认"))
                warning_box.cancelButton.hide()
                warning_box.exec()
                return

            # 创建定时器
            self.scheduled_timer = QTimer(self)
            self.scheduled_timer.setSingleShot(True)
            self.scheduled_timer.timeout.connect(self.start_scheduled_task)
            self.scheduled_timer.start(msec_diff)

            # 更新按钮文本
            time_str = scheduled_time.toString("HH:mm:ss")
            self.schedule_btn.setText(f"{time_str}")

            # 显示提示
            info_cont = f" {time_str} " + self.tra("定时开始任务") + "  ... "
            self.info_toast(self.tra("已设置定时任务，将在"), info_cont)

    # 开始定时任务
    def start_scheduled_task(self) -> None:
        """定时器触发，开始任务"""
        self.info("定时任务已开始 ...")
        self.cancel_scheduled_task() # 清理定时器自身状态

        # 启动任务
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.continue_btn.setEnabled(False)
        self.emit(Base.EVENT.TASK_START, {
            "continue_status": False,
            "current_mode": self.current_mode
        })
        
        # 开启UI刷新器
        self.ui_update_timer.start()

        # 自动展开监控页面
        if not self.arrow_btn.isChecked():
            self.arrow_btn.setChecked(True)
            self.arrowClicked.emit()

    # 取消当前的定时任务
    def cancel_scheduled_task(self):
        """取消当前的定时任务"""
        if self.scheduled_timer:
            self.scheduled_timer.stop()
            self.scheduled_timer = None
        self.schedule_btn.setText(self.tra("定时"))

# 层级浏览器
class NavigationCard(Base,CardWidget):
    searchRequested = pyqtSignal(dict)  # 信号，发送搜索参数字典
    termExtractionRequested = pyqtSignal(dict)  # 用于发送术语提取参数的信号
    languageCheckRequested = pyqtSignal(str)    

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)
        
        self.toolbar = QWidget()
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_layout.setSpacing(0)
        
        # 搜索按钮
        self.search_button = TransparentPushButton(FIF.SEARCH,self.tra("搜索"))
        # 设置合适的大小

        self.search_button.clicked.connect(self._open_search_dialog) # 连接点击事件

        # 术语提取按钮
        self.term_extraction_button = TransparentPushButton(FIF.FILTER, self.tra("术语"))
        self.term_extraction_button.clicked.connect(self._open_term_extraction_dialog)

        # 语言检查按钮
        self.check_button = TransparentPushButton(FIF.EDUCATION, self.tra("检查"))
        self.check_button.clicked.connect(self._open_language_check_dialog)

        # 为三个按钮设置合适的固定宽度
        button_width = 75
        self.search_button.setFixedWidth(button_width)
        self.term_extraction_button.setFixedWidth(button_width)
        self.check_button.setFixedWidth(button_width)

        # 添加按钮到工具栏布局
        self.toolbar_layout.addWidget(self.term_extraction_button)
        self.toolbar_layout.addWidget(self.search_button)
        self.toolbar_layout.addWidget(self.check_button)
        self.layout.addWidget(self.toolbar)
        
        self.tree = TreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.layout.addWidget(self.tree)

    # 搜索按钮事件
    def _open_search_dialog(self):
        dialog = SearchDialog(self.window())
        if dialog.exec():
            # 用户点击了“搜索”并输入了内容
            params = {
                "query": dialog.search_query,
                "is_regex": dialog.is_regex,
                "scope": dialog.search_scope,
                "search_flagged": dialog.is_flagged_search
            }
            self.searchRequested.emit(params)

    # 检查按钮事件
    def _open_language_check_dialog(self):
        dialog = LanguageCheckDialog(self.window())
        if dialog.exec():
            self.languageCheckRequested.emit(dialog.check_mode)
            

    # 按钮点击
    def _open_term_extraction_dialog(self):
        """打开术语提取设置对话框"""
        dialog = TermExtractionDialog(self.window())
        if dialog.exec():
            # 用户点击了“开始提取”
            params = {
                "model_name": dialog.selected_model,
                "entity_types": dialog.selected_types
            }
            self.termExtractionRequested.emit(params)

    # 树状关系更新
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
class PageCard(Base,CardWidget):
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

        # 创建保存按钮
        self.save_button = TransparentToolButton(FIF.SAVE)
        self.save_button.setIconSize(QSize(16, 16))
        self.save_button.clicked.connect(self.on_save_button_clicked)

        # 将按钮添加到按钮容器布局
        button_layout.addWidget(self.view_button)
        button_layout.addWidget(self.save_button)


        # 将 TabBar 和按钮容器添加到水平布局
        tab_layout.addWidget(self.tab_bar, 1)  # 参数 1 表示该控件是可拉伸的
        tab_layout.addWidget(button_container) # 参数 0 (默认) 表示该控件不拉伸，保持原始大小

        # 将水平布局添加到主布局
        self.layout.addLayout(tab_layout)

        # 创建并添加 QStackedWidget
        self.stacked_widget = QStackedWidget(self)
        self.layout.addWidget(self.stacked_widget)

    def on_save_button_clicked(self):
        """
        获取配置中的 label_output_path 并调用手动保存缓存事件。
        不再生成最终翻译文件，只保存项目缓存。
        """
        config = self.load_config()
        output_path = config.get("label_output_path")

        # 检查路径是否存在，如果不存在则尝试创建
        try:
            cache_dir = os.path.join(output_path, "cache")
            if not os.path.isdir(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
        except OSError as e:
            self.error_toast(self.tra("路径错误"), self.tra("创建缓存目录失败: {}").format(e))
            return
        
        # 发出新的手动保存缓存事件
        self.emit(Base.EVENT.TASK_MANUAL_SAVE_CACHE, {"output_path": output_path})
        
        # 给予用户反馈
        self.success_toast(self.tra("成功"), self.tra("项目缓存已保存到输出文件夹"))

    def on_view_button_clicked(self):
        """
        提取当前前台标签页的所有文本，生成新的视图标签页进行美观展示。
        """
        current_index = self.stacked_widget.currentIndex()

        # 处理没有标签页的情况
        if current_index == -1:
            MessageBox(self.tra("提示"), self.tra("当前没有打开的标签页。"), self.window()).exec() # M
            return

        # 获取当前标签页和其数据表格
        current_tab = self.stacked_widget.widget(current_index)

        # 检查当前是否为原始数据表格页，而不是一个视图页
        if not isinstance(current_tab, TabInterface):
            MessageBox(self.tra("提示"), self.tra("请在原始数据表格标签页上执行此操作。"), self.window()).exec() # M
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

        view_tab_name = f"View - {original_tab_name}"
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

# 标签页
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

# 主界面
class EditViewPage(Base,QFrame):

    languageCheckFinished = pyqtSignal(tuple)    

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
        self.nav_card = NavigationCard(window)  # 导航卡片
        self.page_card = PageCard()  # 页面卡片
        self.splitter.addWidget(self.nav_card)
        self.splitter.addWidget(self.page_card)
        self.splitter.setStretchFactor(0, 1) # 左邊 nav_card 佔 1 份
        self.splitter.setStretchFactor(1, 9) # 右邊 page_card 佔 9 份
        self.main_page_layout.addWidget(self.splitter)

        # 隐藏拖拽手柄，以免主题切换不和谐
        self.splitter.setHandleWidth(0)
        self.splitter.setStyleSheet("QSplitter::handle { width: 0px; }")

        # 监控页面设置
        self.monitoring_page = MonitoringPage()

        # 向堆叠控件添加页面，即信息展示页面与监控页面
        self.stacked_widget.addWidget(self.main_page)
        self.stacked_widget.addWidget(self.monitoring_page)

        # 底部命令栏设置
        self.bottom_bar_main = BottomCommandBar(window)

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
        self.nav_card.searchRequested.connect(self.perform_search) # 连接搜索按钮请求信号
        self.nav_card.languageCheckRequested.connect(self.perform_language_check) # 连接语言检查请求信号
        self.startup_page.folderSelected.connect(self.on_folder_selected) # 连接信号到界面切换和路径处理
        self.bottom_bar_main.back_btn.clicked.connect(self.on_back_button_clicked)  # 返回按钮绑定
        self.nav_card.tree.itemClicked.connect(self.on_tree_item_clicked)  # 树形项点击事件
        self.page_card.tab_bar.currentChanged.connect(self.on_tab_changed)  # 标签页切换事件
        self.page_card.tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)  # 标签页关闭请求
        self.bottom_bar_main.arrowClicked.connect(self.toggle_page)  # 箭头按钮点击切换页面
        self.nav_card.termExtractionRequested.connect(self.perform_term_extraction) # 开始术语提取信号

        self.languageCheckFinished.connect(self._on_language_check_finished) #连接检查完成信号到槽函数


        # 订阅事件
        self.subscribe(Base.EVENT.TASK_CONTINUE_CHECK, self.task_continue_check)
        self.subscribe(Base.EVENT.TERM_EXTRACTION_DONE, self._on_term_extraction_finished)
              
        
    # 页面显示事件
    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 触发继续状态检测事件
        self.task_continue_check( event = None, data = None)

    # 继续任务状态检查事件
    def task_continue_check(self, event: int, data: dict) -> None:
        threading.Thread(target = self.task_continue_check_target, daemon=True).start()

    # 继续任务状态检查
    def task_continue_check_target(self) -> None:
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
            # 增强的JSON文件读取，防止并发访问和空文件问题
            max_retries = 3
            retry_delay = 0.1
            
            for attempt in range(max_retries):
                try:
                    # 检查文件大小，避免读取空文件
                    if os.path.getsize(json_file_path) == 0:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        else:
                            print(f"[WARNING] ProjectStatistics.json文件为空，跳过继续检查")
                            return False
                    
                    # 安全读取JSON文件
                    with open(json_file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if not content:
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)
                                continue
                            else:
                                print(f"[WARNING] ProjectStatistics.json内容为空")
                                return False
                        
                        data = json.loads(content)
                        break  # 成功读取，退出重试循环
                        
                except (json.JSONDecodeError, OSError, IOError) as e:
                    if attempt < max_retries - 1:
                        print(f"[WARNING] 读取ProjectStatistics.json失败(尝试{attempt+1}/{max_retries}): {e}")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                        continue
                    else:
                        print(f"[ERROR] 读取ProjectStatistics.json最终失败: {e}")
                        return False
                except Exception as e:
                    print(f"[ERROR] 读取ProjectStatistics.json时发生未知错误: {e}")
                    return False
            
            # 获取数据
            is_continue =  True
            project_name = data.get("project_name") # 获取已项目名字
            total_line = data.get("total_line") # 获取需翻译行数
            line = data.get("line") # 获取已翻译行数

            # 有数据则表示进行过任务,放宽读取范围
            if total_line:
                self.continue_status = True

            # 如果完成了任务，则不显示继续按钮
            if total_line and line >= total_line:
                is_continue = False

        # 根据任务状态，更新界面
        if self.continue_status == True :
            # 启动页显示继续翻译按钮
            self.startup_page.show_continue_button(True)
            # 命令栏启用继续按钮
            if is_continue:
                self.bottom_bar_main.enable_continue_button(True)
            # 在 ActionCard 上显示项目名
            self.startup_page.continue_card.set_project_name(project_name)

        else:
            self.startup_page.show_continue_button(False)
            # 命令栏禁用继续按钮
            self.bottom_bar_main.enable_continue_button(False)

    # 输入文件夹路径改变信号
    def on_folder_selected(self, project_name: str, project_mode: str):
        # 从缓存器获取文件层级结构
        file_hierarchy = self.cache_manager.get_file_hierarchy()
        # 更新导航卡片的树状视图
        self.nav_card.update_tree(file_hierarchy)

        # 更新底部命令栏的项目名
        self.bottom_bar_main.update_project_name(project_name)

        # 根据是否继续状态启用继续按钮
        if project_mode == "new":
            self.bottom_bar_main.enable_continue_button(False)
        else:
            # 启用底部命令栏的继续按钮
            self.bottom_bar_main.enable_continue_button(True)

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
            MessageBox(self.tra("错误"), self.tra("无法从缓存中加载文件: {}").format(file_path), self).exec() # M
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

    # 执行搜索事件
    def perform_search(self, params: dict):
        """执行搜索并显示结果"""
        query = params["query"]
        scope = params["scope"]
        is_regex = params["is_regex"]
        search_flagged = params["search_flagged"]

        self.info(f"正在搜索: '{query}' (范围: {scope}, 正则: {is_regex}, 标记行: {search_flagged})")
        
        # 调用 CacheManager 执行搜索
        results = self.cache_manager.search_items(query, scope, is_regex, search_flagged)

        if not results:
            MessageBox(self.tra("未找到结果"), self.tra("未能找到与 '{}' 匹配的内容。").format(query), self.window()).exec() # M
            return
        
        # 创建搜索结果标签页
        tab_name = f"Search - {query[:20]}..."
        # 使用时间戳确保路由键唯一
        route_key = f"search_{int(time.time())}"

        # 检查是否已存在完全相同的搜索结果页（简单检查名称）
        for i in range(self.page_card.tab_bar.count()):
            if self.page_card.tab_bar.tabText(i) == tab_name:
                self.page_card.tab_bar.setCurrentIndex(i)
                # 同时也要确保内容页面切换
                self.page_card.stacked_widget.setCurrentIndex(i)
                return

        # 创建新的搜索结果页面实例
        search_page = SearchResultPage(results, self.cache_manager, params)
        search_page.setObjectName(route_key)

        # 添加新标签页
        self.page_card.stacked_widget.addWidget(search_page)
        self.page_card.tab_bar.addTab(routeKey=route_key, text=tab_name)

        # 获取新标签页的索引
        new_index = self.page_card.tab_bar.count() - 1
        
        # 显式地同时设置 TabBar 和 StackedWidget 的当前索引
        # 这样可以确保新标签页被激活并显示在前台
        self.page_card.tab_bar.setCurrentIndex(new_index)
        self.page_card.stacked_widget.setCurrentIndex(new_index)


    # 执行语言检查
    def perform_language_check(self, mode: str):
        """在一个单独的线程中执行语言检查"""
        self.info("开始语言检查")
        
        # 使用线程避免UI冻结
        thread = threading.Thread(target=self._language_check_worker, args=(mode,), daemon=True)
        thread.start()

    def _language_check_worker(self, mode: str):
        """工作线程，执行实际的检查并发出信号"""
        checker = TranslationChecker(self.cache_manager)
        result_code, data = checker.check_language(mode)
        self.languageCheckFinished.emit((result_code, data))

    def _on_language_check_finished(self, result: tuple):
        """接收检查结果并在主线程中显示消息框"""
        result_code, data = result
        
        title = self.tra("检查结果")
        msg_box = None

        if result_code == CheckResult.ERROR_CACHE:
            msg_box = MessageBox(title, self.tra("检查失败，请检查项目文件夹缓存是否正常"), self.window())
        elif result_code == CheckResult.ERROR_NO_TRANSLATION:
            msg_box = MessageBox(title, self.tra("检查失败，请先执行翻译流程"), self.window())
        elif result_code == CheckResult.ERROR_NO_POLISH:
            msg_box = MessageBox(title, self.tra("检查失败，请先执行润色流程"), self.window())
        elif result_code == CheckResult.SUCCESS_REPORT:
            msg_box = MessageBox(title, self.tra("检测完成，请查看控制台输出"), self.window())
        elif result_code == CheckResult.SUCCESS_JUDGE_PASS:
            lang = data.get("target_language", "N/A")
            content = self.tra("检查通过：项目的所有文件均符合设定译文预期").format(lang)
            msg_box = MessageBox(title, content, self.window())
        elif result_code == CheckResult.SUCCESS_JUDGE_FAIL:
            lang = data.get("target_language", "N/A")
            content = self.tra("项目的所有文件译文语言占比不正常，请检查标记行和控制台输出").format(lang)
            msg_box = MessageBox(title, content, self.window())
        
        if msg_box:
            msg_box.yesButton.setText(self.tra("确认"))
            msg_box.cancelButton.hide()
            msg_box.exec()  


    # 执行提取术语事件
    def perform_term_extraction(self, params: dict):
        """
        从缓存获取数据，并发起一个全局的术语提取事件。
        """
        self.info(f"收到术语提取请求，参数: {params}")
        
        self.info("正在从缓存中收集所有原文...")
        all_items_to_process = self.cache_manager.get_all_source_items()
        
        self.info(f"数据收集完毕，共 {len(all_items_to_process)} 条。正在发送提取事件...")
        
        # 发送开始事件，将参数和数据传递给 SimpleExecutor
        self.emit(Base.EVENT.TERM_EXTRACTION_START, {
            "params": params,
            "items_data": all_items_to_process
        })

    # 术语提取结束事件
    def _on_term_extraction_finished(self, event: int, data: dict):
        """
        此槽函数在主线程中执行，用于接收 TERM_EXTRACTION_DONE 事件并安全地更新UI。
        """
        results = data.get("results", [])

        if not results:
            MessageBox(self.tra("未找到"), self.tra("未能提取到任何符合条件的术语。"), self.window()).exec()
            return

        # 创建并显示结果标签页 (这部分代码保持不变)
        tab_name = self.tra("术语提取结果")
        route_key = f"terms_{int(time.time())}"

        result_page = TermResultPage(results)
        result_page.setObjectName(route_key)
        
        self.page_card.stacked_widget.addWidget(result_page)
        self.page_card.tab_bar.addTab(routeKey=route_key, text=tab_name)
        
        new_index = self.page_card.tab_bar.count() - 1
        self.page_card.tab_bar.setCurrentIndex(new_index)
        self.page_card.stacked_widget.setCurrentIndex(new_index)
        self.info("术语提取完成，结果已显示。")