import json
import os
import threading
import time
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import (QFrame, QSizePolicy, QTreeWidgetItem,
                             QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QSplitter, QStackedWidget)
from qfluentwidgets import (Action,  CaptionLabel, MessageBox, PrimarySplitPushButton, PushButton, RoundMenu,  ToggleToolButton, TransparentDropDownToolButton, TransparentPushButton, TransparentToolButton,
                            TreeWidget, TabBar, FluentIcon as FIF, CardWidget,
                            ProgressBar)

from Base.Base import Base

from UserInterface.EditView.MonitoringPage import MonitoringPage
from UserInterface.EditView.StartupPage import StartupPage
from ModuleFolders.TaskExecutor.TaskType import TaskType

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
        self.success_toast("", info_cont)

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
        self.layout.setSpacing(8)  # 增加间距
        
        # 添加工具栏到层级浏览器顶部
        self.toolbar = QWidget()
        self.toolbar_layout = QHBoxLayout(self.toolbar)
        self.toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_layout.setSpacing(8)
        
        # 搜索按钮
        self.search_button = TransparentToolButton(FIF.SEARCH)

        # 添加到布局
        self.toolbar_layout.addStretch(1)  
        self.toolbar_layout.addWidget(self.search_button)
        self.toolbar_layout.addStretch(1)  

        # 将工具栏添加到主布局
        self.layout.addWidget(self.toolbar)
        
        # 添加层级浏览器
        self.tree = TreeWidget(self)
        self.layout.addWidget(self.tree)
        
        self.populate_tree()

    def populate_tree(self):
        item1 = QTreeWidgetItem(['JoJo 1 - Phantom Blood'])
        item1.addChildren([
            QTreeWidgetItem(['Jonathan Joestar']),
            QTreeWidgetItem(['Dio Brando']),
            QTreeWidgetItem(['Will A. Zeppeli']),
        ])
        self.tree.addTopLevelItem(item1)

        item2 = QTreeWidgetItem(['JoJo 3 - Stardust Crusaders'])
        item21 = QTreeWidgetItem(['Jotaro Kujo'])
        item21.addChildren([
            QTreeWidgetItem(['空条承太郎']),
            QTreeWidgetItem(['空条蕉太狼']),
            QTreeWidgetItem(['阿强']),
        ])
        item2.addChild(item21)
        self.tree.addTopLevelItem(item2)

        item3 = QTreeWidgetItem(['测试文件'])
        self.tree.addTopLevelItem(item3)

        self.tree.expandAll()
        self.tree.setHeaderHidden(True)

# 标签栏
class PageCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

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

        # 创建功能菜单
        self.function_menu = RoundMenu(parent=self)
        self.function_menu.addAction(Action(FIF.SAVE, 'AI排版'))
        self.function_menu.addAction(Action(FIF.SAVE, 'AI总结'))
        self.function_menu.addSeparator()
        self.function_menu.addAction(Action(FIF.PRINT, '删除翻译'))
        self.function_menu.addAction(Action(FIF.PRINT, '删除润色'))
        self.function_menu.addSeparator()
        self.function_menu.addAction(Action(FIF.SETTING, '当前文件信息'))

        # 创建功能菜单按钮
        self.menu_button = TransparentDropDownToolButton(FIF.MENU)
        self.menu_button.setIconSize(QSize(16, 16))
        self.menu_button.setMenu(self.function_menu)

        # 将按钮添加到按钮容器布局
        button_layout.addWidget(self.view_button)
        button_layout.addWidget(self.menu_button)


        # 将 TabBar 和按钮容器添加到水平布局
        tab_layout.addWidget(self.tab_bar, 1)  # 参数 1 表示该控件是可拉伸的
        tab_layout.addWidget(button_container) # 参数 0 (默认) 表示该控件不拉伸，保持原始大小

        # 将水平布局添加到主布局
        self.layout.addLayout(tab_layout)

        # 创建并添加 QStackedWidget
        self.stacked_widget = QStackedWidget(self)
        self.layout.addWidget(self.stacked_widget)

    def on_view_button_clicked(self):
        """视图切换按钮的占位功能"""
        MessageBox("视图切换", "视图切换按钮被点击", self).exec()

# 标签页
class TabInterface(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel(f"{text} 的页面编辑区域\n（可扩展为表格或其他内容）", self)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignCenter)
        self.setObjectName(text.replace(' ', '-'))

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
        self.startup_page = StartupPage(support_project_types = support_project_types)

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
        self.startup_page.continueButtonPressed.connect(self.show_main_interface_from_startup_continue) # 继续按钮点击具体事件
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
    def on_folder_selected(self, path: str):

        # 获取配置信息
        config = self.load_config()
        translation_project = config.get("translation_project", "AutoType")  # 获取翻译项目类型
        label_input_path = config.get("label_input_path", "./input")   # 获取输入文件夹路径
        label_input_exclude_rule = config.get("label_input_exclude_rule", "")  # 获取输入文件夹排除规则

        # 读取输入文件夹的文件，生成缓存
        self.print("")
        self.info(f"正在读取输入文件夹中的文件 ...")
        try:
            # 读取输入文件夹的文件，生成缓存
            CacheProject = self.file_reader.read_files(
                    translation_project,
                    label_input_path,
                    label_input_exclude_rule
                )
            # 读取完成后，保存到缓存管理器中
            self.cache_manager.load_from_project(CacheProject)

        except Exception as e:
            self.translating = False # 更改状态
            self.error("翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ... ", e)
            return None

        # 检查数据是否为空
        if self.cache_manager.get_item_count() == 0:
            self.translating = False # 更改状态
            self.error("翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ... ")
            return None

        # 输出每个文件的检测信息
        for _, file in self.cache_manager.project.files.items():
            # 获取信息
            language_stats = file.language_stats
            storage_path = file.storage_path
            encoding = file.encoding
            file_project_type = file.file_project_type

            # 输出信息
            self.print("")
            self.info(f"已经载入文件 - {storage_path}")
            self.info(f"文件类型 - {file_project_type}")
            self.info(f"文件编码 - {encoding}")
            self.info(f"语言统计 - {language_stats}")

        self.info(f"项目数据全部载入成功 ...")
        self.print("")

        # 切换到主界面
        self.top_stacked_widget.setCurrentWidget(self.main_interface)

    # 启动页继续项目按钮事件
    def show_main_interface_from_startup_continue(self):
        # 获取配置信息
        config = self.load_config()
        label_output_path = config.get("label_output_path", "./output")   # 获取输入文件夹路径

        # 读取输入文件夹的文件
        self.print("")
        self.info(f"正在读取缓存文件 ...")
        try:
            # 直接读取缓存文件
            self.cache_manager.load_from_file(label_output_path)

        except Exception as e:
            self.translating = False # 更改状态
            self.error("翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ... ", e)
            return None

        # 检查数据是否为空
        if self.cache_manager.get_item_count() == 0:
            self.translating = False # 更改状态
            self.error("翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ... ")
            return None

        # 输出每个文件的检测信息
        for _, file in self.cache_manager.project.files.items():
            # 获取信息
            language_stats = file.language_stats
            storage_path = file.storage_path
            encoding = file.encoding
            file_project_type = file.file_project_type

            # 输出信息
            self.print("")
            self.info(f"已经载入文件 - {storage_path}")
            self.info(f"文件类型 - {file_project_type}")
            self.info(f"文件编码 - {encoding}")
            self.info(f"语言统计 - {language_stats}")

        self.info(f"项目数据全部载入成功 ...")
        self.print("")

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
        tab_text = item.text(0)

        # 使用规范化名称进行比较
        normalized_name = self.normalize_name(tab_text)

        # 检查是否已存在该标签页
        for i in range(self.page_card.tab_bar.count()):
            if self.normalize_name(self.page_card.tab_bar.tabText(i)) == normalized_name:
                self.page_card.tab_bar.setCurrentIndex(i)
                self.page_card.stacked_widget.setCurrentIndex(i)
                return

        # 创建新标签页
        new_tab = TabInterface(tab_text)
        self.page_card.stacked_widget.addWidget(new_tab)
        self.page_card.tab_bar.addTab(tab_text, tab_text)
        new_index = self.page_card.tab_bar.count() - 1
        self.page_card.tab_bar.setCurrentIndex(new_index)

        # 立即切换到新创建的页面
        self.page_card.stacked_widget.setCurrentWidget(new_tab)

    # 标签页点击事件，切换到对应的页面
    def on_tab_changed(self, index):
        if index >= 0:
            tab_text = self.page_card.tab_bar.tabText(index)
            normalized_name = self.normalize_name(tab_text)

            for i in range(self.page_card.stacked_widget.count()):
                widget = self.page_card.stacked_widget.widget(i)
                if self.normalize_name(widget.objectName()) == normalized_name:
                    self.page_card.stacked_widget.setCurrentIndex(i)
                    return

    # 规范化标签页索引名
    def normalize_name(self, name):
        # 删除可能存在的不可见字符
        cleaned = name.strip().replace(' ', '-')
        # 移除其他特殊字符（保留中文字符）
        return ''.join(c for c in cleaned if c.isalnum() or c == '-')

    # 标签页删除事件
    def on_tab_close_requested(self, index):
        tab_text = self.page_card.tab_bar.tabText(index)
        for i in range(self.page_card.stacked_widget.count()):
            if self.page_card.stacked_widget.widget(i).objectName() == tab_text.replace(' ', '-'):
                self.page_card.stacked_widget.removeWidget(self.page_card.stacked_widget.widget(i))
                break
        self.page_card.tab_bar.removeTab(index)