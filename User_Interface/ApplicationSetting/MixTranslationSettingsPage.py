
import os
import json

from rich import print
from PyQt5.Qt import Qt
from PyQt5.Qt import QEvent
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import PillPushButton
from qfluentwidgets import SingleDirectionScrollArea

from Widget.SpinCard import SpinCard
from Widget.GroupCard import GroupCard
from Widget.LineEditCard import LineEditCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard

class MixTranslationSettingsPage(QFrame):

    DEFAULT = {
        "mix_translation_enable": False,
        "mix_translation_settings": {
            "translation_platform_1": "openai",
            "translation_platform_2": "openai",
            "customModel_siwtch_2": False,
            "model_type_2": "",
            "split_switch_2": False,
            "translation_platform_3": "openai",
            "customModel_siwtch_3": False,
            "model_type_3": "",
            "split_switch_3": False
        },
    }

    def __init__(self, text: str, parent, configurator):
        super().__init__(parent = parent)

        self.setObjectName(text.replace(" ", "-"))
        self.configurator = configurator

        # 初始化事件列表
        self.on_show_event = []

        # 载入配置文件
        config = self.load_config()
        config = self.save_config(config)

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)

        # 设置滚动容器
        self.scroller = SingleDirectionScrollArea(self, orient = Qt.Vertical)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container.addWidget(self.scroller)

        # 设置容器
        self.vbox_parent = QWidget(self)
        self.vbox_parent.setStyleSheet("QWidget { background: transparent; }")
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下
        self.scroller.setWidget(self.vbox_parent)

        # 添加控件
        self.add_widget_01(self.vbox, config)
        self.add_widget_02(self.vbox, config)
        self.add_widget_03(self.vbox, config)
        self.add_widget_04(self.vbox, config)

        # 填充
        self.vbox.addStretch(1)

    # 页面每次展示时触发
    def showEvent(self, event: QEvent):
        super().showEvent(event)

        for v in self.on_show_event:
            v(self, event)

    # 载入配置文件
    def load_config(self) -> dict[str]:
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

    # 混合翻译模式
    def add_widget_01(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("mix_translation_enable"))
            
        def widget_callback(widget, checked: bool):
            config["mix_translation_enable"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "混合翻译模式", 
                "启用此功能后，将按照本页中的设置进行多轮次的翻译，主要用于解决翻译残留等问题",
                widget_init,
                widget_callback,
            )
        )

    # 第一轮
    def add_widget_02(self, parent, config):

        def add_translation_platform_1_card(widget):

            def update_widget(widget):
                config = self.load_config()

                widget.set_items(self.get_items(config))
                widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("mix_translation_settings").get("translation_platform_1")))))

            def widget_init(widget):
                # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
                self.on_show_event.append(
                    lambda _, event: update_widget(widget)
                )

            def widget_callback(widget, index: int):
                config = self.load_config()
                
                config["mix_translation_settings"]["translation_platform_1"] = self.find_tag_by_name(config, widget.get_current_text())
                self.save_config(config)

            widget.addWidget(
                ComboBoxCard(
                    "模型类型", 
                    "第一轮翻译中使用的模型类型",
                    [],
                    widget_init,
                    widget_callback,
                )
            )

        def widget_init(widget):
            add_translation_platform_1_card(widget)

        parent.addWidget(
            GroupCard(
                "首轮设置", 
                "这些设置将在进行第一轮翻译时覆盖原有的应用设置",
                widget_init,
            )
        )

    # 第二轮
    def add_widget_03(self, parent, config):

        def add_translation_platform_2_card(parent):
            
            def update_widget(widget):
                config = self.load_config()

                widget.set_items(self.get_items(config))
                widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("mix_translation_settings").get("translation_platform_2")))))

            def widget_init(widget):
                # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
                self.on_show_event.append(
                    lambda _, event: update_widget(widget)
                )

            def widget_callback(widget, index: int):
                config = self.load_config()
                
                config["mix_translation_settings"]["translation_platform_2"] = self.find_tag_by_name(config, widget.get_current_text())
                self.save_config(config)
                
            parent.addWidget(
                ComboBoxCard(
                    "模型类型", 
                    "第二轮翻译中使用的模型类型",
                    [],
                    widget_init,
                    widget_callback,
                )
            )

        def add_custom_model_siwtch_2_card(parent):
            def widget_init(widget):
                model_type_2 = config.get("mix_translation_settings").get("model_type_2")

                if model_type_2 != "":
                    widget.set_text(model_type_2)

                widget.set_placeholder_text("请输入模型名称 ...")

            def widget_callback(widget, text: str):
                text = text.strip()

                if text != "":
                    config["mix_translation_settings"]["model_type_2"] = text
                    config["mix_translation_settings"]["customModel_siwtch_2"] = True
                else:
                    config["mix_translation_settings"]["model_type_2"] = text
                    config["mix_translation_settings"]["customModel_siwtch_2"] = False

                self.save_config(config)

            parent.addWidget(
                LineEditCard(
                    "覆盖模型名称", 
                    "在进行第二轮的翻译时，将使用此模型名称覆盖原有的应用设置，留空为不覆盖原有模型名称",
                    widget_init,
                    widget_callback,
                )
            )
            
        def add_split_switch_2_card(parent):
            def widget_init(widget):
                widget.set_checked(config.get("mix_translation_settings").get("split_switch_2"))
                
            def widget_callback(widget, checked: bool):
                config["mix_translation_settings"]["split_switch_2"] = checked
                self.save_config(config)

            parent.addWidget(
                SwitchButtonCard(
                    "文本对半切分", 
                    "启用此功能后，在第二轮翻译时，文本将默认进行对半切分",
                    widget_init,
                    widget_callback,
                )
            )

        def widget_init(widget):
            add_translation_platform_2_card(widget)
            add_custom_model_siwtch_2_card(widget)
            add_split_switch_2_card(widget)

        parent.addWidget(
            GroupCard(
                "次轮设置", 
                "这些设置将在进行第二轮翻译时覆盖原有的应用设置",
                widget_init,
            )
        )

    # 后续轮次
    def add_widget_04(self, parent, config):

        def add_translation_platform_3_card(parent):
            
            def update_widget(widget):
                config = self.load_config()

                widget.set_items(self.get_items(config))
                widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("mix_translation_settings").get("translation_platform_3")))))

            def widget_init(widget):
                # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
                self.on_show_event.append(
                    lambda _, event: update_widget(widget)
                )

            def widget_callback(widget, index: int):
                config = self.load_config()
                
                config["mix_translation_settings"]["translation_platform_3"] = self.find_tag_by_name(config, widget.get_current_text())
                self.save_config(config)
                
            parent.addWidget(
                ComboBoxCard(
                    "模型类型", 
                    "后续轮次的翻译中使用的模型类型",
                    [],
                    widget_init,
                    widget_callback,
                )
            )

        def add_custom_model_siwtch_3_card(parent):
            def widget_init(widget):
                model_type_3 = config.get("mix_translation_settings").get("model_type_3")

                if model_type_3 != "":
                    widget.set_text(model_type_3)

                widget.set_placeholder_text("请输入模型名称 ...")

            def widget_callback(widget, text: str):
                text = text.strip()

                if text != "":
                    config["mix_translation_settings"]["model_type_3"] = text
                    config["mix_translation_settings"]["customModel_siwtch_3"] = True
                else:
                    config["mix_translation_settings"]["model_type_3"] = text
                    config["mix_translation_settings"]["customModel_siwtch_3"] = False

                self.save_config(config)

            parent.addWidget(
                LineEditCard(
                    "覆盖模型名称", 
                    "在进行后续轮次的翻译时，将使用此模型名称覆盖原有的应用设置，留空为不覆盖原有模型名称",
                    widget_init,
                    widget_callback,
                )
            )
            
        def add_split_switch_3_card(parent):
            def widget_init(widget):
                widget.set_checked(config.get("mix_translation_settings").get("split_switch_3"))
                
            def widget_callback(widget, checked: bool):
                config["mix_translation_settings"]["split_switch_3"] = checked
                self.save_config(config)

            parent.addWidget(
                SwitchButtonCard(
                    "文本对半切分", 
                    "启用此功能后，在进行后续轮次的翻译时，文本将默认进行对半切分",
                    widget_init,
                    widget_callback,
                )
            )

        def widget_init(widget):
            add_translation_platform_3_card(widget)
            add_custom_model_siwtch_3_card(widget)
            add_split_switch_3_card(widget)

        parent.addWidget(
            GroupCard(
                "后续轮次", 
                "这些设置将在进行后续轮次的翻译时覆盖原有的应用设置",
                widget_init,
            )
        )