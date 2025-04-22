from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFrame, QLabel, QLayout, QStackedWidget
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import FluentIcon, SegmentedWidget

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.LineEditCard import LineEditCard
from Widget.PushButtonCard import PushButtonCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.FolderDropCard import FolderDropCard

class ProjectSettingsPage(QFrame, Base):

    def __init__(self, text: str, window, support_project_types: set[str]) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))


        self.pivot = SegmentedWidget(self)  # 创建一个 SegmentedWidget 实例，分段式导航栏
        self.stackedWidget = QStackedWidget(self)  # 创建一个 QStackedWidget 实例，堆叠式窗口
        self.vBoxLayout = QVBoxLayout(self)  # 创建一个垂直布局管理器

        self.A_settings = ProjectSettingsPage_A('A_settings', window)  # 创建实例，指向界面
        self.B_settings = ProjectSettingsPage_B('B_settings', window, support_project_types)  # 创建实例，指向界面

        # 添加子界面到分段式导航栏
        self.addSubInterface(self.A_settings, 'A_settings', '快速设置')
        self.addSubInterface(self.B_settings, 'B_settings', '详细设置')

        # 将分段式导航栏和堆叠式窗口添加到垂直布局中
        self.vBoxLayout.addWidget(self.pivot)
        self.vBoxLayout.addWidget(self.stackedWidget)
        self.vBoxLayout.setContentsMargins(5, 5, 5, 0)  # 分别设置左、上、右、下的边距

        # 连接堆叠式窗口的 currentChanged 信号到槽函数 onCurrentIndexChanged
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.A_settings)  # 设置默认显示的子界面为xxx界面
        self.pivot.setCurrentItem(self.A_settings.objectName())  # 设置分段式导航栏的当前项为xxx界面

    def addSubInterface(self, widget: QLabel, objectName, text):
        """
        添加子界面到堆叠式窗口和分段式导航栏
        """
        widget.setObjectName(objectName)
        #widget.setAlignment(Qt.AlignCenter) # 设置 widget 对象的文本（如果是文本控件）在控件中的水平对齐方式
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget),
        )

    def onCurrentIndexChanged(self, index):
        """
        槽函数：堆叠式窗口的 currentChanged 信号的槽函数
        """
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())


# 快速设置
class ProjectSettingsPage_A(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "target_platform": "deepseek",
            "label_input_path": "./input",
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_folder_drop(self.container, config)
        self.add_widget_api(self.container, config)

        # 填充
        self.container.addStretch(1)

    # 页面每次展示时触发
    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self.show_event(self, event) if hasattr(self, "show_event") else None

    # 获取接口列表
    def get_items(self, config) -> list:
        return [v.get("name") for k, v in config.get("platforms").items()]

    # 通过接口名字获取标签
    def find_tag_by_name(self, config, name: str) -> str:
        results = [v.get("tag") for k, v in config.get("platforms").items() if v.get("name") == name]

        if len(results) > 0:
            return results[0]
        else:
            return ""

    # 通过接口标签获取名字
    def find_name_by_tag(self, config, tag: str) -> str:
        results = [v.get("name") for k, v in config.get("platforms").items() if v.get("tag") == tag]

        if len(results) > 0:
            return results[0]
        else:
            return ""


    # 输入文件夹
    def add_widget_folder_drop(self, parent: QLayout, config: dict) -> None:

        def widget_callback(widget: FolderDropCard, path: str) -> None:
            # path 参数直接由信号提供
            if not path: # 检查路径是否有效
                print("无效的路径或回调触发时路径为空")
                # 重置路径
                widget.reset() 
                return

            #print(f"路径拖放回调触发: {path}") # 调试信息

            # 更新并保存配置
            current_config = self.load_config()
            current_config["label_input_path"] = path.strip()
            self.save_config(current_config)
            #print(f"配置已更新: test_path = {path.strip()}")

        # 获取配置文件中的初始路径
        initial_path = config.get("label_input_path", "") # 使用空字符串作为默认值

        drop_card = FolderDropCard(
            title=self.tra("将输入文件夹拖拽到此处"),
            prompt_text=self.tra("输入文件夹路径"),
            initial_path=initial_path if initial_path else None, # 如果为空则不设置初始路径
            path_dropped_callback=widget_callback,
            parent=self
        )

        parent.addWidget(drop_card)



    # 模型类型
    def add_widget_api(self, parent, config) -> None:

        def update_widget(widget) -> None:
            config = self.load_config()

            widget.set_items(self.get_items(config))
            widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("target_platform")))))

        def init(widget) -> None:
            # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
            self.show_event = lambda _, event: update_widget(widget)

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["target_platform"] = self.find_tag_by_name(config, text)
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("接口平台"),
                self.tra("设置当前翻译项目所使用的接口的名称，注意，选择错误将不能进行翻译"),
                [],
                init = init,
                current_text_changed = current_text_changed,
            )
        )


# 详细设置
class ProjectSettingsPage_B(QFrame, Base):

    def __init__(self, text: str, window, support_project_types: set[str]) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))
        self.support_project_types = support_project_types

        # 默认配置
        self.default = {
            "translation_project": "AutoType",
            "source_language": "japanese",
            "target_language": "chinese_simplified",
            "label_input_exclude_rule": "",
            "label_output_path": "./output",
            "auto_set_output_path": True
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_02(self.container, config)
        self.add_widget_03(self.container, config)
        self.add_widget_04(self.container, config)
        self.add_widget_exclude_rule(self.container, config)
        self.add_widget_06(self.container, config)
        self.add_widget_07(self.container, config)

        # 填充
        self.container.addStretch(1)


    # 项目类型
    def add_widget_02(self, parent, config) -> None:
        # 定义项目类型与值的配对列表（显示文本, 存储值）
        project_pairs = [
            (self.tra("Txt小说文件"), "Txt"),
            (self.tra("Epub小说文件"), "Epub"),
            (self.tra("Docx文档文件"), "Docx"),
            (self.tra("Srt字幕文件"), "Srt"),
            (self.tra("Vtt字幕文件"), "Vtt"),
            (self.tra("Lrc音声文件"), "Lrc"),
            (self.tra("Md文档文件"), "Md"),
            (self.tra("T++导出文件"), "Tpp"),
            (self.tra("Trans工程文件"), "Trans"),
            (self.tra("Mtool导出文件"), "Mtool"),
            (self.tra("Renpy导出文件"), "Renpy"),
            (self.tra("VNText导出文件"), "Vnt"),
            (self.tra("Ainiee缓存文件"), "Ainiee_cache"),
            (self.tra("ParaTranz导出文件"), "Paratranz"),
            (self.tra('Pdf文档文件 (需要Microsoft Office)'), "OfficeConversionPdf"),
            (self.tra('Doc文档文件 (需要Microsoft Office)'), "OfficeConversionDoc"),
            (self.tra("自动识别文件类型"), "AutoType")

        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in project_pairs if value in self.support_project_types]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("translation_project", "AutoType")
            
            # 旧配置兼容层转换(后续版本再删除)
            if current_value == "Txt小说文件":
                current_value = "Txt"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Srt字幕文件":
                current_value = "Srt"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Vtt字幕文件":
                current_value = "Vtt"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Lrc音声文件":
                current_value = "Lrc"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Epub小说文件":
                current_value = "Epub"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Docx文档文件":
                current_value = "Docx"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "Mtool导出文件":
                current_value = "Mtool"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "T++导出文件":
                current_value = "Tpp"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "VNText导出文件":
                current_value = "Vnt"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
            elif current_value == "ParaTranz导出文件":
                current_value = "Paratranz"
                current_config["translation_project"] = current_value
                self.save_config(current_config)
                
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

    # 原文语言
    def add_widget_03(self, parent, config) -> None:
        # 定义语言与值的配对列表（显示文本, 存储值）
        source_language_pairs = [
            (self.tra("日语"), "japanese"),
            (self.tra("英语"), "english"),
            (self.tra("韩语"), "korean"),
            (self.tra("俄语"), "russian"),
            (self.tra("德语"), "german"),
            (self.tra("法语"), "french"),
            (self.tra("简中"), "chinese_simplified"),
            (self.tra("繁中"), "chinese_traditional"),
            (self.tra("西班牙语"), "spanish"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in source_language_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("source_language", "japanese")
            

            # 旧配置兼容层转换(后续版本再删除)
            if current_value == "日语":
                current_value = "japanese"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "英语":
                current_value = "english"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "韩语":
                current_value = "korean"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "俄语":
                current_value = "russian"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "德语":
                current_value = "german"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "法语":
                current_value = "french"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "简中":
                current_value = "chinese_simplified"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "繁中":
                current_value = "chinese_traditional"
                current_config["source_language"] = current_value
                self.save_config(current_config)
            elif current_value == "西班牙语":
                current_value = "spanish"
                current_config["source_language"] = current_value
                self.save_config(current_config)


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
                "japanese"  # 默认值
            )
            
            config = self.load_config()
            config["source_language"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, _ in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("原文语言"),
                self.tra("设置当前翻译项目所使用的原始文本的语言，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    # 译文语言
    def add_widget_04(self, parent, config) -> None:
        # 定义语言与值的配对列表（显示文本, 存储值）
        target_language_pairs = [
            (self.tra("简中"), "chinese_simplified"),
            (self.tra("繁中"), "chinese_traditional"),
            (self.tra("英语"), "english"),
            (self.tra("日语"), "japanese"),
            (self.tra("韩语"), "korean"),
            (self.tra("俄语"), "russian"),
            (self.tra("德语"), "german"),
            (self.tra("法语"), "french"),
            (self.tra("西班牙语"), "spanish"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in target_language_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("target_language", "chinese_simplified")
            
            # 旧配置兼容层转换(后续版本再删除)
            if current_value == "日语":
                current_value = "japanese"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "英语":
                current_value = "english"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "韩语":
                current_value = "korean"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "俄语":
                current_value = "russian"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "德语":
                current_value = "german"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "法语":
                current_value = "french"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "简中":
                current_value = "chinese_simplified"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "繁中":
                current_value = "chinese_traditional"
                current_config["target_language"] = current_value
                self.save_config(current_config)
            elif current_value == "西班牙语":
                current_value = "spanish"
                current_config["target_language"] = current_value
                self.save_config(current_config)


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
                "chinese_simplified"  # 默认值
            )
            
            config = self.load_config()
            config["target_language"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, _ in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("译文语言"),
                self.tra("设置当前翻译项目所期望的译文文本的语言，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

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

    # 输出文件夹
    def add_widget_06(self, parent, config) -> None:
        def widget_init(widget):
            info_cont = self.tra("当前输出文件夹为") + f" {config.get("label_output_path")}"
            widget.set_description(info_cont)
            widget.set_text(self.tra("选择文件夹"))
            widget.set_icon(FluentIcon.FOLDER_ADD)

        def widget_callback(widget) -> None:
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(None, "选择文件夹", "")
            if path == None or path == "":
                return

            # 更新UI
            info_cont = self.tra("当前输出文件夹为") + f" {path.strip()}"
            widget.set_description(info_cont)

            # 更新并保存配置
            config = self.load_config()
            config["label_output_path"] = path.strip()
            self.save_config(config)

        parent.addWidget(
            PushButtonCard(
                self.tra("输出文件夹(不能与输入文件夹相同)"),
                "",
                widget_init,
                widget_callback,
            )
        )

    # 自动设置输出文件夹开关
    def add_widget_07(self, parent, config) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("auto_set_output_path"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_set_output_path"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动设置输出文件夹"),
                self.tra("启用此功能后，设置为输入文件夹的平级目录，比如输入文件夹为D:/Test/Input，输出文件夹将设置为D:/Test/AiNieeOutput"),
                widget_init,
                widget_callback,
            )
        )