import threading
from PyQt5.QtWidgets import QLayout, QVBoxLayout, QWidget
from qfluentwidgets import pyqtSignal, StateToolTip
from qfluentwidgets.components.date_time.calendar_picker import FIF

from Base.Base import Base
from Widget.LineEditCard import LineEditCard
from Widget.FolderDropCard import FolderDropCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.ActionCard import ActionCard

class StartupPage(Base, QWidget):
    """开始页面"""
    folderSelected = pyqtSignal(str, str)  # 信号：通知主界面文件夹已选好，切换页面
    loadSuccess = pyqtSignal(str, str)     # 信号(子线程->主线程)：项目加载成功
    loadFailed = pyqtSignal(str)           # 信号(子线程->主线程)：项目加载失败

    def __init__(self, support_project_types=None, parent=None, cache_manager=None, file_reader=None):
        super().__init__(parent)
        self.support_project_types = support_project_types
        self.cache_manager = cache_manager
        self.file_reader = file_reader
        self.stateTooltip = None  # 用于显示状态提示

        # 连接子线程信号到主线程的槽函数
        self.loadSuccess.connect(self._on_load_success)
        self.loadFailed.connect(self._on_load_failed)

        # 默认配置
        self.default = {
            "translation_project": "AutoType",
            "label_input_path": "./input",
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        # 添加组件

        self.add_widget_projecttype(self.container, config)
        self.add_widget_folder_drop(self.container, config)

        # 添加“继续项目”入口
        self.continue_card = ActionCard(
            title=self.tra("继续项目"),
            description=self.tra("加载上次的项目缓存并继续"),
            button_text=self.tra("继续"),
            icon=FIF.RIGHT_ARROW,
            parent=self
        )
        self.continue_card.hide()
        self.continue_card.clicked.connect(lambda: self.folder_path_changed("continue"))
        self.container.addWidget(self.continue_card)

        # 添加弹簧
        self.container.addStretch(1)

    def show_continue_button(self, show: bool) -> None:
        """显示或隐藏继续按钮入口"""
        if show:
            self.continue_card.show()
        else:
            self.continue_card.hide()

    def add_widget_projecttype(self, parent, config) -> None:
        """项目类型"""
        translated_pairs = [(self.tra(project_type), project_type) for project_type in self.support_project_types]

        def init(widget) -> None:
            current_config = self.load_config()
            current_value = current_config.get("translation_project", "AutoType")
            index = next((i for i, (_, value) in enumerate(translated_pairs) if value == current_value), 0)
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            value = next((value for display, value in translated_pairs if display == text), "AutoType")
            config = self.load_config()
            config["translation_project"] = value
            self.save_config(config)

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

    def add_widget_folder_drop(self, parent: QLayout, config: dict) -> None:
        """输入文件夹"""
        def widget_callback(path: str) -> None:
            current_config = self.load_config()
            current_config["label_input_path"] = path.strip()
            self.save_config(current_config)
            self.folder_path_changed("new")

        initial_path = config.get("label_input_path", "./input")
        # 将 drag_card 保存为实例属性，以便后续禁用/启用
        self.drag_card = FolderDropCard(
            init=initial_path,
            path_changed=widget_callback,
        )
        parent.addWidget(self.drag_card)

    def folder_path_changed(self, mode: str) -> None:
        """
        [主线程] 用户点击按钮或输入文件夹后调用此方法。
        它负责启动UI提示并开启一个子线程来执行耗时的加载任务。
        """
        # 显示加载提示
        if self.stateTooltip:
            self.stateTooltip.close()
        
        self.stateTooltip = StateToolTip(self.tra('正在加载项目...'), self.tra('客官请耐心等待哦~~'), self.window())
        # 将提示工具移动到窗口上方居中的位置
        x = self.window().width() // 2 - self.stateTooltip.width() // 2
        y = 32  # 设置一个固定的顶部边距
        self.stateTooltip.move(x, y)
        self.stateTooltip.show()

        # 禁用输入控件，防止重复操作
        self.drag_card.setEnabled(False)
        self.continue_card.setEnabled(False)

        # 在子线程中执行加载任务
        loader_thread = threading.Thread(target=self._load_project_worker, args=(mode,), daemon=True)
        loader_thread.start()

    def _load_project_worker(self, mode: str) -> None:
        """
        [子线程] 执行实际的文件读取和缓存加载工作。
        完成后通过信号通知主线程结果。
        """
        try:
            config = self.load_config()
            translation_project = config.get("translation_project", "AutoType")
            label_input_path = config.get("label_input_path", "./input")
            label_input_exclude_rule = config.get("label_input_exclude_rule", "")
            label_output_path = config.get("label_output_path", "./output")

            if mode == "new":
                CacheProject = self.file_reader.read_files(
                    translation_project,
                    label_input_path,
                    label_input_exclude_rule
                )
                self.cache_manager.load_from_project(CacheProject)
            else:  # "continue"
                self.cache_manager.load_from_file(label_output_path)

            if self.cache_manager.get_item_count() == 0:
                raise ValueError("项目数据为空，可能是项目类型或输入文件夹设置不正确。")

            project_name = self.cache_manager.project.project_name
            self.loadSuccess.emit(project_name, mode)

        except Exception as e:
            error_message = "翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ..."
            self.error(error_message, e)
            self.loadFailed.emit(error_message)

    def _on_load_success(self, project_name: str, project_mode: str) -> None:
        """
        [主线程] 接收加载成功信号后的处理函数。
        """
        # 更新UI提示为成功状态
        if self.stateTooltip:
            info = self.tra('项目加载成功！') + '🚀'
            self.stateTooltip.setContent(self.tra(info))
            self.stateTooltip.setState(True)
            self.stateTooltip = None  # 重置以便下次使用

        # 重新启用控件
        self.drag_card.setEnabled(True)
        self.continue_card.setEnabled(True)

        # 打印文件信息到控制台
        self.print("")
        self.info(f"项目数据全部载入成功 ...")
        for _, file in self.cache_manager.project.files.items():
            language_stats = file.language_stats
            storage_path = file.storage_path
            encoding = file.encoding
            file_project_type = file.file_project_type

            self.print("")
            self.info(f"已经载入文件 - {storage_path}")
            self.info(f"文件类型 - {file_project_type}")
            self.info(f"文件编码 - {encoding}")
            self.info(f"语言统计 - {language_stats}")
        self.print("")

        # 发送最终信号，通知主界面切换页面
        self.folderSelected.emit(project_name, project_mode)

    def _on_load_failed(self, error_message: str) -> None:
        """
        [主线程] 接收加载失败信号后的处理函数。
        """
        # 更新UI提示为失败状态
        if self.stateTooltip:
            info = self.tra('加载失败...') + '😵'
            self.stateTooltip.setContent(self.tra(info))
            self.stateTooltip.setState(False)
            self.stateTooltip = None  # 重置以便下次使用

        # 重新启用控件
        self.drag_card.setEnabled(True)
        self.continue_card.setEnabled(True)

        # 弹出错误提示
        self.error_toast(self.tra("错误"), error_message)