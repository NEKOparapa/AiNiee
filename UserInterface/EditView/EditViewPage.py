import sys
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QLineEdit, QMainWindow, QTreeWidgetItem,
                             QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QPushButton, QSplitter, QStackedWidget, QGridLayout)
from qfluentwidgets import (DropDownPushButton, PrimaryPushButton, PushButton,
                            TreeWidget, TabBar, FluentIcon as FIF, CardWidget,
                            ProgressBar)

class CustomToolbar(CardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(55)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 5, 8, 5)
        self.layout.setSpacing(8)

        # Create buttons
        self.button1 = DropDownPushButton(FIF.MAIL, "搜索")
        self.button2 = DropDownPushButton(FIF.MAIL, "替换")
        self.button3 = DropDownPushButton(FIF.MAIL, "总结")

        button_icon_size = QSize(18, 18)
        button_height = 32

        for btn in [self.button1, self.button2, self.button3]:
            btn.setIconSize(button_icon_size)
            btn.setFixedHeight(button_height)

        self.layout.addWidget(self.button1)
        self.layout.addWidget(self.button2)
        self.layout.addWidget(self.button3)
        self.layout.addStretch(1)

class BottomCommandBar(CardWidget):
    arrowClicked = pyqtSignal()

    def __init__(self, arrow_direction="up", parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 5, 8, 5)
        self.layout.setSpacing(12)

        # 返回按钮
        self.back_btn = PushButton(FIF.RETURN, "返回")
        self.back_btn.setIconSize(QSize(16, 16))
        self.back_btn.setFixedHeight(32)

        # 项目信息区域
        project_widget = QWidget()
        project_layout = QVBoxLayout(project_widget)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(8)

        # 项目名称和进度状态
        top_row = QHBoxLayout()
        self.project_name = QLabel('项目名字')
        self.project_name.setFixedWidth(200)
        self.progress_status = QLabel("235/1578")
        top_row.addWidget(self.project_name, alignment=Qt.AlignLeft)
        top_row.addStretch()
        top_row.addWidget(self.progress_status, alignment=Qt.AlignRight)

        # 进度条
        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(45)
        self.progress_bar.setMinimumWidth(400)

        project_layout.addStretch(1)
        project_layout.addLayout(top_row)
        project_layout.addWidget(self.progress_bar)
        project_layout.addStretch(1)

        # 操作按钮
        self.translate_btn = PrimaryPushButton(FIF.LANGUAGE, '一键翻译')
        self.polish_btn = PrimaryPushButton(FIF.EDIT, '润色')
        self.arrow_btn = PushButton()
        if arrow_direction == "up":
            self.arrow_btn.setIcon(FIF.UP)
        else:
            self.arrow_btn.setIcon(FIF.DOWN)
        self.arrow_btn.setIconSize(QSize(16, 16))
        self.arrow_btn.setFixedHeight(32)

        for btn in [self.translate_btn, self.polish_btn, self.arrow_btn]:
            btn.setIconSize(QSize(16, 16))
            btn.setFixedHeight(32)

        # 组装布局
        self.layout.addWidget(self.back_btn)
        self.layout.addStretch(1)
        self.layout.addWidget(project_widget)
        self.layout.addStretch(1)
        self.layout.addWidget(self.translate_btn)
        self.layout.addWidget(self.polish_btn)
        self.layout.addWidget(self.arrow_btn)

        # 连接信号
        self.arrow_btn.clicked.connect(self.on_arrow_clicked)

    def on_arrow_clicked(self):
        self.arrowClicked.emit()

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

class TabInterface(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel(f"{text} 的页面编辑区域\n（可扩展为表格或其他内容）", self)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignCenter)
        self.setObjectName(text.replace(' ', '-'))

class DrawerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        # 使用 QGridLayout 模拟流式布局
        self.content_layout = QGridLayout()
        num_columns = 3
        for i in range(10):
            btn = QPushButton(f"测试按钮 {i+1}")
            row = i // num_columns
            col = i % num_columns
            self.content_layout.addWidget(btn, row, col)

        self.layout.addLayout(self.content_layout)
        self.layout.addStretch(1)

        # 添加底部工具栏，箭头向下
        self.bottom_bar = BottomCommandBar(arrow_direction="down")
        self.layout.addWidget(self.bottom_bar)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Text Management App')
        self.resize(1600, 900)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # 主布局
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 添加组件
        self.custom_toolbar = CustomToolbar()
        self.splitter = QSplitter(Qt.Horizontal)
        self.nav_card = NavigationCard()
        self.page_card = PageCard()
        self.splitter.addWidget(self.nav_card)
        self.splitter.addWidget(self.page_card)
        self.splitter.setSizes([200, 800])

        # 创建主页面
        self.main_page = QWidget()
        self.main_page_layout = QVBoxLayout(self.main_page)
        self.main_page_layout.addWidget(self.splitter)
        self.bottom_bar_main = BottomCommandBar(arrow_direction="up")
        self.main_page_layout.addWidget(self.bottom_bar_main)

        # 创建抽屉页面
        self.drawer_page = DrawerPage()

        # 使用 QStackedWidget 管理页面
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.main_page)
        self.stacked_widget.addWidget(self.drawer_page)
        self.stacked_widget.setCurrentIndex(0)

        # 组装主界面
        self.main_layout.addWidget(self.custom_toolbar)
        self.main_layout.addWidget(self.stacked_widget)

        # 连接信号
        self.nav_card.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.page_card.tab_bar.currentChanged.connect(self.on_tab_changed)
        self.page_card.tab_bar.tabCloseRequested.connect(self.on_tab_close_requested)
        self.bottom_bar_main.arrowClicked.connect(self.toggle_page)
        self.drawer_page.bottom_bar.arrowClicked.connect(self.toggle_page)

    def toggle_page(self):
        current_index = self.stacked_widget.currentIndex()
        new_index = 1 - current_index
        self.stacked_widget.setCurrentIndex(new_index)

    def on_tree_item_clicked(self, item, column):
        tab_text = item.text(0)
        for i in range(self.page_card.tab_bar.count()):
            if self.page_card.tab_bar.tabText(i) == tab_text:
                self.page_card.tab_bar.setCurrentIndex(i)
                return
        new_tab = TabInterface(tab_text)
        self.page_card.stacked_widget.addWidget(new_tab)
        self.page_card.tab_bar.addTab(tab_text, tab_text)
        self.page_card.tab_bar.setCurrentIndex(self.page_card.tab_bar.count() - 1)

    def on_tab_changed(self, index):
        if index >= 0:
            tab_text = self.page_card.tab_bar.tabText(index)
            for i in range(self.page_card.stacked_widget.count()):
                if self.page_card.stacked_widget.widget(i).objectName() == tab_text.replace(' ', '-'):
                    self.page_card.stacked_widget.setCurrentIndex(i)
                    break

    def on_tab_close_requested(self, index):
        tab_text = self.page_card.tab_bar.tabText(index)
        for i in range(self.page_card.stacked_widget.count()):
            if self.page_card.stacked_widget.widget(i).objectName() == tab_text.replace(' ', '-'):
                self.page_card.stacked_widget.removeWidget(self.page_card.stacked_widget.widget(i))
                break
        self.page_card.tab_bar.removeTab(index)

if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())