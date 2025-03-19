from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import FluentIcon

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.PushButtonCard import PushButtonCard

class ProjectSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "target_platform": "deepseek",
            "translation_project": "Txt",
            "source_language": "japanese",
            "target_language": "chinese_simplified",
            "label_input_path": "./input",
            "label_output_path": "./output",
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_01(self.container, config)
        self.add_widget_02(self.container, config)
        self.add_widget_03(self.container, config)
        self.add_widget_04(self.container, config)
        self.add_widget_05(self.container, config)
        self.add_widget_06(self.container, config)

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

    # 模型类型
    def add_widget_01(self, parent, config) -> None:

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
                self.tra("接口名称"),
                self.tra("设置当前翻译项目所使用的接口的名称，注意，选择错误将不能进行翻译"),
                [],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

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
            (self.tra("Mtool导出文件"), "Mtool"),
            (self.tra("Renpy导出文件"), "Renpy"),
            (self.tra("VNText导出文件"), "Vnt"),
            (self.tra("Ainiee缓存文件"), "Ainiee_cache"),
            (self.tra("ParaTranz导出文件"), "Paratranz"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in project_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("translation_project", "Txt")
            
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
                "Txt"  # 默认值
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

    # 输入文件夹
    def add_widget_05(self, parent, config) -> None:
        def widget_init(widget) -> None:
            info_cont = self.tra("当前输入文件夹为") + f" {config.get("label_input_path")}"
            widget.set_description(info_cont)
            widget.set_text(self.tra("选择文件夹"))
            widget.set_icon(FluentIcon.FOLDER_ADD)

        def widget_callback(widget) -> None:
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(None,  self.tra("选择文件夹"), "")
            if path == None or path == "":
                return

            # 更新UI
            info_cont = self.tra("当前输入文件夹为") + f" {path.strip()}"
            widget.set_description(info_cont)

            # 更新并保存配置
            config = self.load_config()
            config["label_input_path"] = path.strip()
            self.save_config(config)

        parent.addWidget(
            PushButtonCard(
                self.tra("输入文件夹"),
                "",
                widget_init,
                widget_callback,
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