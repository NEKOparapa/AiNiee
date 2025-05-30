import json
import os
import threading
import time
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import (QFrame, QLayout, QTreeWidgetItem,
                             QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QSplitter, QStackedWidget)
from qfluentwidgets import (Action,  CaptionLabel, FlowLayout, PrimarySplitPushButton, PushButton, RoundMenu,  ToggleToolButton, TransparentDropDownPushButton, TransparentPushButton, 
                            TreeWidget, TabBar, FluentIcon as FIF, CardWidget,
                            ProgressBar)

from Base.Base import Base
from Widget.DashboardCard import DashboardCard
from Widget.WaveformCard import WaveformCard
from Widget.LineEditCard import LineEditCard
from Widget.ProgressRingCard import ProgressRingCard
from Widget.FolderDropCard import FolderDropCard
from Widget.CombinedLineCard import CombinedLineCard
from Widget.ComboBoxCard import ComboBoxCard

from ModuleFolders.Cache.CacheProject import ProjectType

# 开始页面
class StartupPage(Base,QWidget):
    folderSelected = pyqtSignal(str)  # 定义信号，用于通知文件夹路径选择

    def __init__(self, support_project_types=None, parent=None):
        super().__init__(parent)
        self.support_project_types = support_project_types

        # 默认配置
        self.default = {
            "label_input_exclude_rule": "",
            "translation_project": "AutoType",
            "label_input_path": "./input",
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加组件
        self.add_widget_exclude_rule(self.container, config)
        self.add_widget_projecttype(self.container, config)
        self.add_widget_folder_drop(self.container, config)

        # 填充
        self.container.addStretch(1)


    # 输入的文件/目录排除规则
    def add_widget_exclude_rule(self, parent, config) -> None:

        def init(widget) -> None:
            widget.set_text(config.get("label_input_exclude_rule"))
            widget.set_fixed_width(256)
            widget.set_placeholder_text(self.tra("*.log,aaa/*"))

        def text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["label_input_exclude_rule"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("输入文件/目录排除规则"),
                self.tra("*.log 表示排除所有结尾为 .log 的文件，aaa/* 表示排除输入文件夹下整个 aaa 目录，多个规则用英文逗号分隔"),
                init=init,
                text_changed=text_changed,
            )
        )

    # 项目类型
    def add_widget_projecttype(self, parent, config) -> None:
        # 定义项目类型与值的配对列表（显示文本, 存储值）
        project_pairs = [
            (self.tra("Txt小说文件"), ProjectType.TXT),
            (self.tra("Epub小说文件"), ProjectType.EPUB),
            (self.tra("Docx文档文件"), ProjectType.DOCX),
            (self.tra("Srt字幕文件"), ProjectType.SRT),
            (self.tra("Vtt字幕文件"), ProjectType.VTT),
            (self.tra("Lrc音声文件"), ProjectType.LRC),
            (self.tra("Md文档文件"), ProjectType.MD),
            (self.tra("T++导出文件"), ProjectType.TPP),
            (self.tra("Trans工程文件"), ProjectType.TRANS),
            (self.tra("Mtool导出文件"), ProjectType.MTOOL),
            (self.tra("Renpy导出文件"), ProjectType.RENPY),
            (self.tra("VNText导出文件"), ProjectType.VNT),
            (self.tra("I18Next数据文件"), ProjectType.I18NEXT),
            (self.tra("ParaTranz导出文件"), ProjectType.PARATRANZ),
            (self.tra('Doc文档文件 (需要Microsoft Office)'), ProjectType.OFFICE_CONVERSION_DOC),
            (self.tra('Pdf文档文件 (pdf2zh/BabelDOC)'), ProjectType.BABELDOC_PDF),
            (self.tra("自动识别文件类型"), ProjectType.AUTO_TYPE)

        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in project_pairs if value in self.support_project_types]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("translation_project", "AutoType")
            
            # 通过值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时存储对应的值"""
            # 通过显示文本查找对应的值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "AutoType"  # 默认值
            )
            
            config = self.load_config()
            config["translation_project"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, value in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("项目类型"),
                self.tra("设置当前翻译项目所使用的原始文本的格式，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    # 输入文件夹
    def add_widget_folder_drop(self, parent: QLayout, config: dict) -> None:

        def widget_callback(path: str) -> None:
            # 更新并保存配置
            current_config = self.load_config()
            current_config["label_input_path"] = path.strip()
            self.save_config(current_config)

            # 发出信号通知文件夹已选择
            self.folderSelected.emit(path)

        # 获取配置文件中的初始路径
        initial_path = config.get("label_input_path", "./input")

        drag_card = FolderDropCard(
            init=initial_path,  # 传入初始路径
            path_changed=widget_callback,
        )
        parent.addWidget(drag_card)


# 顶部工具栏
class CustomToolbar(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(55)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 5, 8, 5)
        self.layout.setSpacing(8)

        self.button1 = TransparentDropDownPushButton(FIF.SEARCH, "搜索")
        self.button2 = TransparentDropDownPushButton(FIF.MAIL, "筛选")
        self.button3 = TransparentDropDownPushButton(FIF.MAIL, "提取")
        self.button4 = TransparentDropDownPushButton(FIF.MAIL, "处理")
        self.button5 = TransparentPushButton(FIF.SHARE, "导出")

        button_icon_size = QSize(18, 18)
        button_height = 32

        for btn in [self.button1, self.button2, self.button3]:
            btn.setIconSize(button_icon_size)
            btn.setFixedHeight(button_height)

        self.layout.addWidget(self.button1)
        self.layout.addWidget(self.button2)
        self.layout.addWidget(self.button3)
        self.layout.addWidget(self.button4)
        self.layout.addWidget(self.button5)
        self.layout.addStretch(1)

# 底部命令栏
class BottomCommandBar(CardWidget):
    arrowClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 5, 8, 5)
        self.layout.setSpacing(12)

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
        self.progress_status = CaptionLabel("235/1578")
        self.progress_status.setTextColor("#404040") 
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

        self.menu = RoundMenu(parent=self)
        self.menu.addAction(Action(FIF.BASKETBALL, '开始校正'))
        self.menu.addAction(Action(FIF.ALBUM, '开始润色'))

        self.start_btn = PrimarySplitPushButton(FIF.PLAY, '开始翻译')
        self.start_btn.setFlyout(self.menu)
        self.continue_btn = TransparentPushButton(FIF.ROTATE, '继续')
        self.stop_btn = TransparentPushButton(FIF.CANCEL_MEDIUM, '终止')
        self.schedule_btn = TransparentPushButton(FIF.DATE_TIME, '定时')
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
        self.layout.addWidget(self.arrow_btn)

        self.arrow_btn.clicked.connect(self.on_arrow_clicked)

    def on_arrow_clicked(self):
        self.arrowClicked.emit()

# 层级浏览器
class NavigationCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tree = TreeWidget(self)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
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

# 信息展示框
class PageCard(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(0)
        self.tab_bar = TabBar(self)
        self.tab_bar.setTabMaximumWidth(220)
        self.tab_bar.setTabShadowEnabled(False)
        self.tab_bar.setTabSelectedBackgroundColor(Qt.white, Qt.lightGray)
        self.tab_bar.setScrollable(True)
        self.layout.addWidget(self.tab_bar)
        self.stacked_widget = QStackedWidget(self)
        self.layout.addWidget(self.stacked_widget)

# 具体展示页
class TabInterface(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel(f"{text} 的页面编辑区域\n（可扩展为表格或其他内容）", self)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignCenter)
        self.setObjectName(text.replace(' ', '-'))

# 监控页面
class DrawerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)  # 左、上、右、下

        # 添加控件
        self.head_hbox_container = QWidget(self)
        self.head_hbox = FlowLayout(self.head_hbox_container, needAni=False)
        self.head_hbox.setSpacing(8)
        self.head_hbox.setContentsMargins(0, 0, 0, 0)

        # 添加卡片控件
        self.add_combined_line_card(self.head_hbox)
        self.add_token_card(self.head_hbox)
        self.add_task_card(self.head_hbox)
        self.add_time_card(self.head_hbox)
        self.add_remaining_time_card(self.head_hbox)
        self.add_ring_card(self.head_hbox)
        self.add_waveform_card(self.head_hbox)
        self.add_speed_card(self.head_hbox)
        self.add_stability_card(self.head_hbox)

        # 添加到主容器
        self.container.addWidget(self.head_hbox_container, 1)

    # 进度环
    def add_ring_card(self, parent: QLayout) -> None:
        self.ring = ProgressRingCard(title="任务进度",
                                    icon=FIF.PIE_SINGLE,
                                    min_value=0,
                                    max_value=10000,
                                    ring_size=(140, 140),
                                    text_visible=True)
        self.ring.setFixedSize(204, 204)
        self.ring.set_format("无任务")
        parent.addWidget(self.ring)

    # 波形图
    def add_waveform_card(self, parent: QLayout) -> None:
        self.waveform = WaveformCard("波形图",
                                    icon=FIF.MARKET
                                    )
        self.waveform.set_draw_grid(False)  # 关闭网格线
        self.waveform.setFixedSize(633, 204)
        parent.addWidget(self.waveform)

    # 累计时间
    def add_time_card(self, parent: QLayout) -> None:
        self.time = DashboardCard(
                title="累计时间",
                value="Time",
                unit="",
                icon=FIF.STOP_WATCH,
            )
        self.time.setFixedSize(204, 204)
        parent.addWidget(self.time)

    # 剩余时间
    def add_remaining_time_card(self, parent: QLayout) -> None:
        self.remaining_time = DashboardCard(
                title="剩余时间",
                value="Time",
                unit="",
                icon=FIF.FRIGID,
            )
        self.remaining_time.setFixedSize(204, 204)
        parent.addWidget(self.remaining_time)

    # 行数统计
    def add_combined_line_card(self, parent: QLayout) -> None:

        self.combined_line_card = CombinedLineCard(
            title="行数统计",
            icon=FIF.PRINT, 
            left_title="已完成",
            right_title="剩余",
            initial_left_value="0",   
            initial_left_unit="Line",
            initial_right_value="0", 
            initial_right_unit="Line",
            parent=self
        )

        self.combined_line_card.setFixedSize(416, 204) 
        parent.addWidget(self.combined_line_card)

    # 平均速度
    def add_speed_card(self, parent: QLayout) -> None:
        self.speed = DashboardCard(
                title="平均速度",
                value="T/S",
                unit="",
                icon=FIF.SPEED_HIGH,
            )
        self.speed.setFixedSize(204, 204)
        parent.addWidget(self.speed)

    # 累计消耗
    def add_token_card(self, parent: QLayout) -> None:
        self.token = DashboardCard(
                title="累计消耗",
                value="Token",
                unit="",
                icon=FIF.CALORIES,
            )
        self.token.setFixedSize(204, 204)
        parent.addWidget(self.token)

    # 并行任务
    def add_task_card(self, parent: QLayout) -> None:
        self.task = DashboardCard(
                title="实时任务数",
                value="0",
                unit="",
                icon=FIF.SCROLL,
            )
        self.task.setFixedSize(204, 204)
        parent.addWidget(self.task)

    # 稳定性
    def add_stability_card(self, parent: QLayout) -> None:
        self.stability = DashboardCard(
                title="任务稳定性",
                value="%",
                unit="",
                icon=FIF.TRAIN,
            )
        self.stability.setFixedSize(204, 204)
        parent.addWidget(self.stability)

# 主界面
class EditViewPage(Base,QFrame):

    def __init__(self, text: str, window,support_project_types) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 创建主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 四周边距归零
        main_layout.setSpacing(0)  # 控件间距归零
        
        # 顶级堆叠控件，用于切换启动页和主界面
        self.top_stacked_widget = QStackedWidget()
        main_layout.addWidget(self.top_stacked_widget)

        # 创建启动页面
        self.startup_page = StartupPage(support_project_types = support_project_types)

        # 创建主界面控件
        self.main_interface = QWidget()
        self.main_interface_layout = QVBoxLayout(self.main_interface)
        self.main_interface_layout.setContentsMargins(0, 0, 0, 0)  # 四周边距归零
        self.main_interface_layout.setSpacing(0)  # 控件间距归零

        # 向主界面添加工具栏和堆叠控件
        self.custom_toolbar = CustomToolbar()
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
        self.drawer_page = DrawerPage()

        # 向堆叠控件添加页面，即信息展示页面与监控页面
        self.stacked_widget.addWidget(self.main_page)
        self.stacked_widget.addWidget(self.drawer_page)

        # 底部命令栏设置
        self.bottom_bar_main = BottomCommandBar()

        # 组装主界面
        self.main_interface_layout.addWidget(self.custom_toolbar)
        self.main_interface_layout.addWidget(self.stacked_widget)
        self.main_interface_layout.addWidget(self.bottom_bar_main)

        # 向顶级堆叠控件添加启动页面与主页面
        self.top_stacked_widget.addWidget(self.startup_page)
        self.top_stacked_widget.addWidget(self.main_interface)

        # 设置初始页面
        self.top_stacked_widget.setCurrentIndex(0)  # 默认显示启动页

        # 连接各种信号
        self.startup_page.folderSelected.connect(self.on_folder_selected) # 连接信号到界面切换和路径处理
        self.bottom_bar_main.back_btn.clicked.connect(lambda: self.top_stacked_widget.setCurrentIndex(0))  # 返回按钮绑定
        self.nav_card.tree.itemClicked.connect(self.on_tree_item_clicked)  # 树形项点击事件
        self.page_card.tab_bar.currentChanged.connect(self.on_tab_changed)  # 标签页切换事件
        self.page_card.tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)  # 标签页关闭请求
        self.bottom_bar_main.arrowClicked.connect(self.toggle_page)  # 箭头按钮点击切换页面

    # 页面显示事件
    def showEvent(self, event) -> None:
        super().showEvent(event)

        # 重置 UI 状态
        #self.action_continue.setEnabled(False)

        # 触发继续状态检测事件
        self.translation_continue_check()


    # 继续翻译状态检查事件
    def translation_continue_check(self) -> None:
        threading.Thread(target = self.translation_continue_check_target).start()

    # 继续翻译状态检查
    def translation_continue_check_target(self) -> None:
        # 等一下，等页面切换效果结束再执行，避免争抢 CPU 资源，导致 UI 卡顿
        time.sleep(0.5)

        # 检查结果的默认值
        self.continue_status = False

        # 只有翻译状态为 无任务 时才执行检查逻辑，其他情况默认值
        if Base.work_status == Base.STATUS.IDLE:
            config = self.load_config()

            # 过渡方案，通过状态数据小文件来判断

            cache_folder_path = os.path.join(config.get("label_output_path"), "cache")

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
            pass
            #self.top_stacked_widget.setCurrentIndex(1) # 切换到主界面



    # 处理拖拽文件夹路径改变信号
    def on_folder_selected(self, path: str):
        print(f"切换到主界面，选择的文件夹: {path}")
        self.top_stacked_widget.setCurrentIndex(1)  # 切换到主界面


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

    # 标签切换
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

    # 标签删除事件
    def on_tab_close_requested(self, index):
        tab_text = self.page_card.tab_bar.tabText(index)
        for i in range(self.page_card.stacked_widget.count()):
            if self.page_card.stacked_widget.widget(i).objectName() == tab_text.replace(' ', '-'):
                self.page_card.stacked_widget.removeWidget(self.page_card.stacked_widget.widget(i))
                break
        self.page_card.tab_bar.removeTab(index)
