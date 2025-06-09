from PyQt5.QtWidgets import QHBoxLayout, QLayout, QVBoxLayout, QWidget
from qfluentwidgets import PushButton, pyqtSignal
from qfluentwidgets.components.date_time.calendar_picker import FIF

from Base.Base import Base
from Widget.LineEditCard import LineEditCard
from Widget.FolderDropCard import FolderDropCard
from Widget.ComboBoxCard import ComboBoxCard

# 开始页面
class StartupPage(Base,QWidget):
    folderSelected = pyqtSignal(str)  # 定义信号，用于通知文件夹路径选择
    continueButtonPressed = pyqtSignal() # 定义信号，当继续按钮被点击时发出

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

        # 添加“继续”按钮
        self.bottom_button_layout = QHBoxLayout()
        self.continue_button = PushButton(FIF.CARE_RIGHT_SOLID, self.tra("继续项目"), self)
        self.continue_button.setFixedWidth(120) # 可以根据需要调整宽度
        self.continue_button.setFixedHeight(32)
        self.continue_button.hide() # 初始隐藏
        self.continue_button.clicked.connect(self.continueButtonPressed.emit) # 点击时发出信号
        self.bottom_button_layout.addStretch(1) 
        self.bottom_button_layout.addWidget(self.continue_button)
        self.bottom_button_layout.addStretch(1) 
        self.container.addLayout(self.bottom_button_layout) # 将按钮布局添加到主容器

        # 添加弹簧
        self.container.addStretch(1)

    # 显示隐藏继续按钮
    def show_continue_button(self, show: bool) -> None:
        if show:
            self.continue_button.show()
        else:
            self.continue_button.hide()


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
                self.tra("输入文件/目录排除规则"),
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

            # 发出信号通知文件夹已选择
            self.folderSelected.emit(path)

        # 获取配置文件中的初始路径
        initial_path = config.get("label_input_path", "./input")

        drag_card = FolderDropCard(
            init=initial_path,  # 传入初始路径
            path_changed=widget_callback,
        )
        parent.addWidget(drag_card)

