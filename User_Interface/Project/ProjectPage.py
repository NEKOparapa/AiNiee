
import os
import json

from rich import print
from PyQt5.Qt import QEvent
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import FluentIcon

from Widget.SpinCard import SpinCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.PushButtonCard import PushButtonCard

class ProjectPage(QFrame):

    DEFAULT = {
        "translation_platform": "SakuraLLM",
        "translation_project": "Mtool导出文件",
        "source_language": "日语",
        "target_language": "简中",
        "label_input_path": ".\input",
        "label_output_path": ".\output",
    }

    def __init__(self, text: str, parent = None, configurator = None):
        super().__init__(parent = parent)

        self.setObjectName(text.replace(" ", "-"))
        self.configurator = configurator

        # 载入配置文件
        config = self.load_config()
        config = self.save_config(config)

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
        
        if self.on_show_event is not None:
            self.on_show_event(self, event)

    # 载入配置文件
    def load_config(self) -> dict:
        config = {}

        if os.path.exists(os.path.join(self.configurator.resource_dir, "config.json")):
            with open(os.path.join(self.configurator.resource_dir, "config.json"), "r", encoding = "utf-8") as reader:
                config = json.load(reader)

        return config

    # 保存配置文件
    def save_config(self, new: dict) -> None:
        path = os.path.join(self.configurator.resource_dir, "config.json")
        
        # 读取配置文件
        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                old = json.load(reader)
        else:
            old = {}

        # 修改配置文件中的条目：如果条目存在，这更新值，如果不存在，则设置默认值
        for k, v in self.DEFAULT.items():
            if not k in new.keys():
                old[k] = v
            else:
                old[k] = new[k]

        # 写入配置文件
        with open(path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(old, indent = 4, ensure_ascii = False))

        return old

    # 模型类型
    def add_widget_01(self, parent, config):

        def get_items(config) -> list:
            items = [
                "Cohere",
                "Google",
                "OpenAI",
                "Moonshot",
                "Deepseek",
                "Anthropic",
                "Dashscope",
                "SakuraLLM",
                "Volcengine",
                "智谱",
                "零一万物",
                "代理平台A",
            ]

            for k, v in config.get("additional_platform_dict", {}).items():
                items.append(v)

            return items

        def update_widget(widget):
            config = self.load_config()

            widget.set_items(get_items(config))
            widget.set_current_index(max(0, widget.find_text(config.get("translation_platform"))))

        def widget_init(widget):
            # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
            self.on_show_event = lambda _, event: update_widget(widget)
            
        def widget_callback(widget, index: int):
            config["translation_platform"] = widget.get_current_text()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "模型类型",
                "设置当前翻译项目所使用的模型的类型，注意，选择错误将不能进行翻译",
                [],
                widget_init,
                widget_callback,
            )
        )

    # 项目类型
    def add_widget_02(self, parent, config):
        def widget_init(widget):
            widget.set_current_index(max(0, widget.find_text(config.get("translation_project"))))

        def widget_callback(widget, index: int):
            config["translation_project"] = widget.get_current_text()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "项目类型",
                "设置当前翻译项目所使用的原始文本的格式，注意，选择错误将不能进行翻译",
                [
                    "Txt小说文件",
                    "Srt字幕文件",
                    "Lrc音声文件",
                    "T++导出文件",
                    "Epub小说文件",
                    "Mtool导出文件",
                    "VNText导出文件",
                    "Ainiee缓存文件",
                    "ParaTranz导出文件",
                ],
                widget_init,
                widget_callback,
            )
        )

    # 原文语言
    def add_widget_03(self, parent, config):
        def widget_init(widget):
            widget.set_current_index(max(0, widget.find_text(config.get("source_language"))))

        def widget_callback(widget, index: int):
            config["source_language"] = widget.get_current_text()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "原文语言",
                "设置当前翻译项目所使用的原始文本的语言，注意，选择错误将不能进行翻译",
                ["日语", "英语", "韩语", "俄语", "简中", "繁中"],
                widget_init,
                widget_callback,
            )
        )
        
    # 译文语言
    def add_widget_04(self, parent, config):
        def widget_init(widget):
            widget.set_current_index(max(0, widget.find_text(config.get("target_language"))))

        def widget_callback(widget, index: int):
            config["target_language"] = widget.get_current_text()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "译文语言",
                "设置当前翻译项目所期望的译文文本的语言，注意，选择错误将不能进行翻译",
                ["简中", "繁中", "日语", "英语", "韩语"],
                widget_init,
                widget_callback,
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
            widget.set_description(f"当前输出文件夹为 {config.get("label_input_path")}")
            
            # 更新并保存配置
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
            widget.set_description(f"当前输出文件夹为 {config.get("label_output_path")}")
            widget.set_text("选择文件夹")
            widget.set_icon(FluentIcon.FOLDER_ADD)

        def widget_callback(widget, index: int):
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(None, "选择文件夹", "")
            if path == None or path == "":
                return

            # 更新UI
            widget.set_description(f"当前输出文件夹为 {config.get("label_output_path")}")

            # 更新并保存配置
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