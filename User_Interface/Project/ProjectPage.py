from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import FluentIcon

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.PushButtonCard import PushButtonCard

class ProjectPage(QFrame, Base):

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "target_platform": "deepseek",
            "translation_project": "Mtool导出文件",
            "source_language": "日语",
            "target_language": "简中",
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
    def showEvent(self, event: QEvent):
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
    def add_widget_01(self, parent, config):

        def update_widget(widget):
            config = self.load_config()

            widget.set_items(self.get_items(config))
            widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("target_platform")))))

        def init(widget):
            # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
            self.show_event = lambda _, event: update_widget(widget)

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["target_platform"] = self.find_tag_by_name(config, text)
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "接口名称",
                "设置当前翻译项目所使用的接口的名称，注意，选择错误将不能进行翻译",
                [],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 项目类型
    def add_widget_02(self, parent, config):
        def init(widget):
            widget.set_current_index(max(0, widget.find_text(config.get("translation_project"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["translation_project"] = text
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "项目类型",
                "设置当前翻译项目所使用的原始文本的格式，注意，选择错误将不能进行翻译",
                [
                    "Txt小说文件",
                    "Srt字幕文件",
                    "Vtt字幕文件",
                    "Lrc音声文件",
                    "T++导出文件",
                    "Epub小说文件",
                    "Docx文档文件",
                    "Mtool导出文件",
                    "VNText导出文件",
                    "Ainiee缓存文件",
                    "ParaTranz导出文件",
                ],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 原文语言
    def add_widget_03(self, parent, config):
        def init(widget):
            widget.set_current_index(max(0, widget.find_text(config.get("source_language"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["source_language"] = text
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "原文语言",
                "设置当前翻译项目所使用的原始文本的语言，注意，选择错误将不能进行翻译",
                ["日语", "英语", "韩语", "俄语", "简中", "繁中"],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 译文语言
    def add_widget_04(self, parent, config):
        def init(widget):
            widget.set_current_index(max(0, widget.find_text(config.get("target_language"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["target_language"] = text
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "译文语言",
                "设置当前翻译项目所期望的译文文本的语言，注意，选择错误将不能进行翻译",
                ["简中", "繁中", "日语", "英语", "韩语"],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 输入文件夹
    def add_widget_05(self, parent, config):
        def widget_init(widget):
            widget.set_description(f"当前输入文件夹为 {config.get("label_input_path")}")
            widget.set_text("选择文件夹")
            widget.set_icon(FluentIcon.FOLDER_ADD)

        def widget_callback(widget):
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(None, "选择文件夹", "")
            if path == None or path == "":
                return

            # 更新UI
            widget.set_description(f"当前输入文件夹为 {path.strip()}")

            # 更新并保存配置
            config = self.load_config()
            config["label_input_path"] = path.strip()
            self.save_config(config)

        parent.addWidget(
            PushButtonCard(
                "输入文件夹",
                "",
                widget_init,
                widget_callback,
            )
        )

    # 输出文件夹
    def add_widget_06(self, parent, config):
        def widget_init(widget):
            widget.set_description(f"当前输出文件夹(*不能与输入相同)为 {config.get("label_output_path")}")
            widget.set_text("选择文件夹")
            widget.set_icon(FluentIcon.FOLDER_ADD)

        def widget_callback(widget):
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(None, "选择文件夹", "")
            if path == None or path == "":
                return

            # 更新UI
            widget.set_description(f"当前输出文件夹为 {path.strip()}")

            # 更新并保存配置
            config = self.load_config()
            config["label_output_path"] = path.strip()
            self.save_config(config)

        parent.addWidget(
            PushButtonCard(
                "输出文件夹",
                "",
                widget_init,
                widget_callback,
            )
        )