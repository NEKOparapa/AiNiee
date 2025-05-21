import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QAction, QToolBar, QTreeView, QFileSystemModel, QDockWidget,
    QTabWidget, QTableView, QAbstractItemView, QHeaderView,
    QStatusBar, QMessageBox, QInputDialog, QLineEdit,
    QPushButton, QLabel, QSpacerItem, QSizePolicy, QMenu
)
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QDir, QModelIndex

# 建议为你的图标准备一个资源文件夹
# ICON_PATH = "icons/" # 例如: ICON_PATH + "search.png"
# 为了简单起见，这里使用Qt内置图标或不使用图标

class TextManagementApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("文本内容管理编辑器")
        self.setGeometry(100, 100, 1200, 800)

        self.opened_files_tabs = {} # 用于跟踪已打开的文件，避免重复打开

        self._create_actions()
        self._create_tool_bar()
        self._create_menu_bar() # 菜单栏，包含视图切换
        self._create_status_bar()
        self._create_file_browser_dock()
        self._create_main_content_area()

        self.show_status_message("应用程序已启动")

    def _create_actions(self):
        # --- Toolbar Actions ---
        self.search_action = QAction(QIcon(), "搜索", self) # QIcon(ICON_PATH + "search.png")
        self.search_action.setStatusTip("搜索文本内容")
        self.search_action.triggered.connect(self.on_search)

        self.filter_action = QAction(QIcon(), "筛选", self)
        self.filter_action.setStatusTip("筛选表格内容")
        self.filter_action.triggered.connect(self.on_filter)

        self.batch_process_action = QAction(QIcon(), "批量处理", self)
        self.batch_process_action.setStatusTip("对选定内容进行批量处理")
        self.batch_process_action.triggered.connect(self.on_batch_process)

        # --- Menu Actions (for toggling visibility) ---
        self.toggle_toolbar_action = None # 会在创建工具栏后赋值
        self.toggle_file_browser_action = None # 会在创建Dock后赋值
        
        self.exit_action = QAction("退出", self)
        self.exit_action.triggered.connect(self.close)


    def _create_tool_bar(self):
        self.main_toolbar = self.addToolBar("主工具栏")
        self.main_toolbar.setObjectName("MainToolBar") # Для сохранения состояния
        self.main_toolbar.addAction(self.search_action)
        self.main_toolbar.addAction(self.filter_action)
        self.main_toolbar.addAction(self.batch_process_action)
        
        # Action to toggle this toolbar (will be added to View menu)
        self.toggle_toolbar_action = self.main_toolbar.toggleViewAction()
        self.toggle_toolbar_action.setText("显示/隐藏 主工具栏")


    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("文件")
        file_menu.addAction(self.exit_action)

        # View Menu (for tool visibility)
        view_menu = menu_bar.addMenu("视图")
        if self.toggle_toolbar_action:
             view_menu.addAction(self.toggle_toolbar_action)
        # toggle_file_browser_action will be added after dock creation


    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def show_status_message(self, message, timeout=3000):
        self.status_bar.showMessage(message, timeout)

    def _create_file_browser_dock(self):
        self.file_browser_dock = QDockWidget("文件浏览器", self)
        self.file_browser_dock.setObjectName("FileBrowserDock")
        self.file_browser_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(QDir.rootPath()) # Display entire file system
        # Or set a specific project root:
        # project_path = os.path.expanduser("~") # Example: User's home directory
        # self.fs_model.setRootPath(project_path)


        self.file_tree_view = QTreeView()
        self.file_tree_view.setModel(self.fs_model)
        # self.file_tree_view.setRootIndex(self.fs_model.index(project_path)) # If using specific project root

        # Hide unnecessary columns like size, type, date modified for a cleaner look
        self.file_tree_view.setColumnHidden(1, True) # Size
        self.file_tree_view.setColumnHidden(2, True) # Type
        self.file_tree_view.setColumnHidden(3, True) # Date Modified
        
        self.file_tree_view.setHeaderHidden(True) # Hide header if only name is shown
        self.file_tree_view.setAnimated(True) # Nice expand/collapse animation
        self.file_tree_view.doubleClicked.connect(self.on_file_tree_double_clicked)

        self.file_browser_dock.setWidget(self.file_tree_view)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_browser_dock)

        # Action to toggle this dock widget (add to View menu)
        self.toggle_file_browser_action = self.file_browser_dock.toggleViewAction()
        self.toggle_file_browser_action.setText("显示/隐藏 文件浏览器")
        
        # Add to view menu if it exists
        view_menu = self.menuBar().findChild(QMenu, "视图") # findChild is not ideal, better to store menu ref
        if view_menu: # Check if view_menu was created
            view_menu.addAction(self.toggle_file_browser_action)
        else: # Fallback if menu structure changes
            fallback_menu = self.menuBar().addMenu("视图") # Create if not exists
            if self.toggle_toolbar_action: fallback_menu.addAction(self.toggle_toolbar_action)
            fallback_menu.addAction(self.toggle_file_browser_action)


    def _create_main_content_area(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.setCentralWidget(self.tab_widget)

    def on_file_tree_double_clicked(self, index: QModelIndex):
        file_path = self.fs_model.filePath(index)
        if self.fs_model.isDir(index):
            self.show_status_message(f"选择了文件夹: {file_path}")
            # Optionally expand/collapse or set as new root for a sub-view
        else:
            if os.path.isfile(file_path):
                self.open_file_in_new_tab(file_path)
            else:
                self.show_status_message(f"无法识别的文件或路径: {file_path}", 5000)

    def open_file_in_new_tab(self, file_path, content_type="file"):
        if file_path in self.opened_files_tabs:
            # File is already open, switch to its tab
            tab_index = self.opened_files_tabs[file_path]
            if tab_index < self.tab_widget.count(): # Check if tab still exists
                 self.tab_widget.setCurrentIndex(tab_index)
                 self.show_status_message(f"切换到已打开文件: {os.path.basename(file_path)}")
                 return
            else: # Tab was closed, remove from tracking
                del self.opened_files_tabs[file_path]


        try:
            # For simplicity, we assume text files and create a dummy table
            # In a real app, you'd parse the file content based on its type
            
            table_view = QTableView()
            model = QStandardItemModel() # Rows, Columns
            
            if content_type == "file":
                # Example: assume a CSV-like structure or simple lines
                # This is a placeholder. You'll need proper file parsing.
                model.setHorizontalHeaderLabels(["行号", "原文", "译文(可选)", "润色文(可选)"])
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            line = line.strip()
                            item_num = QStandardItem(str(i + 1))
                            item_orig = QStandardItem(line)
                            item_trans = QStandardItem("") # Placeholder for translation
                            item_proof = QStandardItem("") # Placeholder for proofread
                            item_num.setEditable(False)
                            model.appendRow([item_num, item_orig, item_trans, item_proof])
                except Exception as e:
                    QMessageBox.warning(self, "文件读取错误", f"无法读取文件 {file_path}:\n{e}")
                    return
                tab_name = os.path.basename(file_path)

            elif content_type == "search_result":
                model.setHorizontalHeaderLabels(["来源文件", "匹配行号", "匹配内容"])
                # Populate with search results (passed as an argument typically)
                # For now, add dummy data
                model.appendRow([QStandardItem("dummy_file.txt"), QStandardItem("10"), QStandardItem("Search found this!")])
                tab_name = f"搜索结果: {file_path}" # file_path here might be search query
            
            else: # Other content types
                model.setHorizontalHeaderLabels(["列1", "列2", "列3"])
                tab_name = f"自定义页面: {file_path}"


            table_view.setModel(model)
            table_view.setAlternatingRowColors(True)
            table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
            table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Stretch last column
            table_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive) # Allow original text column resize


            # Add search bar and filter bar specific to this tab
            page_widget = QWidget()
            page_layout = QVBoxLayout(page_widget)
            
            # Tab-specific controls (e.g., search within this table)
            # control_layout = QHBoxLayout()
            # control_layout.addWidget(QLabel("页内搜索:"))
            # control_layout.addWidget(QLineEdit())
            # control_layout.addWidget(QPushButton("搜索"))
            # control_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            # page_layout.addLayout(control_layout)

            page_layout.addWidget(table_view)
            page_widget.setProperty("file_path", file_path) # Store filepath for tab closing logic

            idx = self.tab_widget.addTab(page_widget, tab_name)
            self.tab_widget.setCurrentIndex(idx)
            self.opened_files_tabs[file_path] = idx
            self.show_status_message(f"已打开: {tab_name}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开或处理文件时出错: {e}")
            self.show_status_message(f"错误: {e}", 5000)


    def on_tab_close_requested(self, index):
        widget = self.tab_widget.widget(index)
        if widget:
            file_path = widget.property("file_path")
            if file_path and file_path in self.opened_files_tabs:
                del self.opened_files_tabs[file_path]
            # Update other tab indices if necessary (more complex if you re-order tabs)
            # For simplicity, this example doesn't handle index shifting in opened_files_tabs perfectly
            # if tabs are reordered by user. A list of (path, widget) tuples might be better.
            
            # Re-evaluate indices in opened_files_tabs
            # This is a simplified way, might need refinement if tabs can be reordered by user
            temp_opened_files = {}
            for i in range(self.tab_widget.count()):
                if i == index: continue # Skip the tab being closed
                current_widget = self.tab_widget.widget(i if i < index else i-1) # Adjust index for lookup
                path_prop = current_widget.property("file_path") if current_widget else None
                if path_prop:
                     # Find which original path maps to this widget
                    for p, old_idx in list(self.opened_files_tabs.items()): # Use list for safe iteration
                        if old_idx == (i if i < index else i+1): # Check against original index
                           temp_opened_files[p] = i if i < index else i-1 # Store new index
                           break 
            self.opened_files_tabs = temp_opened_files


        self.tab_widget.removeTab(index)
        self.show_status_message("标签页已关闭")


    # --- Placeholder Slots for Toolbar Actions ---
    def on_search(self):
        query, ok = QInputDialog.getText(self, "全局搜索", "输入搜索内容:")
        if ok and query:
            self.show_status_message(f"开始搜索: {query}")
            # Implement actual search logic here
            # For demonstration, open a new tab as if it's a search result
            self.open_file_in_new_tab(query, content_type="search_result")
        else:
            self.show_status_message("搜索已取消")

    def on_filter(self):
        current_tab_widget = self.tab_widget.currentWidget()
        if not current_tab_widget:
            self.show_status_message("没有活动的标签页可供筛选")
            return
        
        # Assuming the current tab's widget is the QWidget containing QTableView
        # Find the QTableView within the current tab
        table_view = current_tab_widget.findChild(QTableView)
        if not table_view or not table_view.model():
            self.show_status_message("当前标签页没有可筛选的表格")
            return
            
        filter_text, ok = QInputDialog.getText(self, "筛选表格", "输入筛选关键词 (针对当前表格):")
        if ok: # Note: 'filter_text' can be empty if user just clicks OK
            self.show_status_message(f"筛选当前表格: '{filter_text}' (功能待实现)")
            # Implement actual filtering logic on table_view.model()
            # This usually involves QSortFilterProxyModel
            QMessageBox.information(self, "筛选", "筛选功能待实现。\n您需要使用 QSortFilterProxyModel 来过滤当前表格的行。")
        else:
            self.show_status_message("筛选已取消")


    def on_batch_process(self):
        self.show_status_message("批量处理功能待实现")
        QMessageBox.information(self, "批量处理", "批量处理功能待实现。\n您需要定义具体的批量操作。")

    def closeEvent(self, event):
        # Save application state (e.g., open tabs, window geometry) if needed
        # For example, using QSettings
        # settings = QSettings("MyCompany", "TextManagerApp")
        # settings.setValue("geometry", self.saveGeometry())
        # settings.setValue("windowState", self.saveState())
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # You can set a style, e.g., "Fusion", "Windows", "GTK+"
    # app.setStyle("Fusion") 
    main_win = TextManagementApp()
    main_win.show()
    sys.exit(app.exec_())