from PyQt5.QtWidgets import  QLayout, QVBoxLayout, QWidget
from qfluentwidgets import  pyqtSignal
from qfluentwidgets.components.date_time.calendar_picker import FIF

from Base.Base import Base
from Widget.LineEditCard import LineEditCard
from Widget.FolderDropCard import FolderDropCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.ActionCard import ActionCard

# 开始页面
class StartupPage(Base,QWidget):
    folderSelected = pyqtSignal(str)  # 定义信号，用于通知文件夹路径选择

    def __init__(self, support_project_types=None, parent=None,cache_manager = None, file_reader = None):
        super().__init__(parent)
        self.support_project_types = support_project_types
        self.cache_manager = cache_manager  # 缓存管理器
        self.file_reader = file_reader  # 文件读取器        

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

        # 添加“继续项目”入口
        self.continue_card = ActionCard(
            title=self.tra("继续项目"),
            description=self.tra("加载上次的项目缓存并继续"),
            button_text=self.tra("继续"),
            icon=FIF.RIGHT_ARROW,
            parent=self
        )
        self.continue_card.hide()  # 初始隐藏
        self.continue_card.clicked.connect(lambda: self.folder_path_changed("continue"))
        self.container.addWidget(self.continue_card) #直接将卡片添加到主容器

        # 添加弹簧
        self.container.addStretch(1)

    # 显示隐藏继续按钮入口
    def show_continue_button(self, show: bool) -> None:
        if show:
            self.continue_card.show()
        else:
            self.continue_card.hide()

    # 文件/目录排除规则
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
                self.tra("文件/目录排除规则"),
                self.tra("*.log 表示排除所有结尾为 .log 的文件，aaa/* 表示排除输入文件夹下整个 aaa 目录，多个规则用英文逗号分隔"),
                init=init,
                text_changed=text_changed,
            )
        )

    # 项目类型
    def add_widget_projecttype(self, parent, config) -> None:

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(project_type), project_type) for project_type in self.support_project_types]

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

            # 文件夹输入事件
            self.folder_path_changed("new")

        # 获取配置文件中的初始路径
        initial_path = config.get("label_input_path", "./input")

        drag_card = FolderDropCard(
            init=initial_path,  # 传入初始路径
            path_changed=widget_callback,
        )
        parent.addWidget(drag_card)

    # 文件夹路径更新事件
    def folder_path_changed(self,mode) -> None:

        # 获取配置信息
        config = self.load_config()
        translation_project = config.get("translation_project", "AutoType")  # 获取翻译项目类型
        label_input_path = config.get("label_input_path", "./input")   # 获取输入文件夹路径
        label_input_exclude_rule = config.get("label_input_exclude_rule", "")  # 获取输入文件夹排除规则
        label_output_path = config.get("label_output_path", "./output")   # 获取输出文件夹路径

        # 读取输入文件夹的文件，生成缓存
        self.print("")
        try:
            
            # 新项目
            if mode and mode == "new":
                self.info(f"正在读取输入文件夹中的文件 ...")
                # 读取输入文件夹的文件，生成缓存
                CacheProject = self.file_reader.read_files(
                        translation_project,
                        label_input_path,
                        label_input_exclude_rule
                    )
                
                # 读取完成后，保存到缓存管理器中
                self.cache_manager.load_from_project(CacheProject)

            # 旧项目
            else:
                self.info(f"正在读取缓存文件 ...")
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


        # 发出信号通知文件夹已选择
        self.folderSelected.emit(mode)

