from PyQt5.QtCore import Qt
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import SingleDirectionScrollArea

from Base.Base import Base
from Widget.GroupCard import GroupCard
from Widget.LineEditCard import LineEditCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard

class MixTranslationSettingsPage(QFrame, Base):

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "mix_translation_enable": False,
            "mix_translation_settings": {
                "translation_platform_1": "openai",
                "translation_platform_2": "openai",
                "model_type_2": "",
                "split_switch_2": True,
                "translation_platform_3": "openai",
                "model_type_3": "",
                "split_switch_3": True,
            },
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 初始化事件列表
        self.on_show_event = []

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

    # 获取接口列表
    def get_items(self, config) -> list:
        return [v.get("name") for k, v in config.get("platforms").items()]

    # 获取模型列表
    def get_model_datas_by_platform(self, config, target_platform: str) -> list | None:
        """
        根据平台tag获取对应的model_datas列表
        
        :param platforms_data: platforms字典结构数据
        :param target_platform: 需要查找的平台tag（如"custom_platform_109186"）
        :return: 匹配平台的model_datas列表，未找到则返回None
        """
        platforms_data = config.get("platforms")
        platform = platforms_data.get(target_platform)
        if platform:
            return platform.get("model_datas")
        return None

    # 通过接口名字获取标签
    def find_tag_by_name(self, config, name: str) -> str:
        results = [v.get("tag") for k, v in config.get("platforms").items() if v.get("name") == name]
        print(f"find_tag_by_name results: {results}")
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
            config = self.load_config()
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

            def init(widget):
                # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
                self.on_show_event.append(
                    lambda _, event: update_widget(widget)
                )

            def current_text_changed(widget, text: str):
                config = self.load_config()

                config["mix_translation_settings"]["translation_platform_1"] = self.find_tag_by_name(config, text)
                self.save_config(config)

            widget.addWidget(
                ComboBoxCard(
                    "模型类型",
                    "第一轮翻译中使用的模型类型",
                    [],
                    init = init,
                    current_text_changed = current_text_changed,
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

            def init(widget):
                # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
                self.on_show_event.append(
                    lambda _, event: update_widget(widget)
                )

            def current_text_changed(widget, text: str):
                config = self.load_config()

                config["mix_translation_settings"]["translation_platform_2"] = self.find_tag_by_name(config, text)
                self.info(f"platform_2: {config.get('mix_translation_settings').get('translation_platform_2')}")
                self.save_config(config)

            parent.addWidget(
                ComboBoxCard(
                    "模型类型",
                    "第二轮翻译中使用的模型类型",
                    [],
                    init = init,
                    current_text_changed = current_text_changed,
                )
            )

        def add_custom_model_siwtch_2_card(parent):
            def update_widget(widget):
                config = self.load_config()
                # 改成下拉选择
                platform = config.get("mix_translation_settings").get("translation_platform_2")
                model_datas = self.get_model_datas_by_platform(config, platform)
                print(f"model_datas: {model_datas}")
                widget.set_items(model_datas)
                model = config.get("mix_translation_settings").get("model_type_2")
                self.info(f"model: {model}")
                widget.set_current_index(max(0, widget.find_text(model)))
            
            def widget_init(widget):
                # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
                self.on_show_event.append(
                    lambda _, event: update_widget(widget)
                )

            def widget_callback(widget, text: str):
                config = self.load_config()
                print(f"text: {text}")
                model_name = text.strip()
                self.info(f"model_name: {model_name}")
                config["mix_translation_settings"]["model_type_2"] = model_name
                self.save_config(config)

            parent.addWidget(
                ComboBoxCard(
                    "覆盖模型名称",
                    "在进行第二轮的翻译时，将使用此模型名称覆盖原有的应用设置，留空为不覆盖原有模型名称",
                    [],
                    init=widget_init,
                    current_text_changed=widget_callback,
                )
            )

        def add_split_switch_2_card(parent):
            def widget_init(widget):
                widget.set_checked(config.get("mix_translation_settings").get("split_switch_2"))

            def widget_callback(widget, checked: bool):
                config = self.load_config()
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

            def init(widget):
                # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
                self.on_show_event.append(
                    lambda _, event: update_widget(widget)
                )

            def current_text_changed(widget, text: str):
                config = self.load_config()

                config["mix_translation_settings"]["translation_platform_3"] = self.find_tag_by_name(config, text)
                self.save_config(config)

            parent.addWidget(
                ComboBoxCard(
                    "模型类型",
                    "后续轮次的翻译中使用的模型类型",
                    [],
                    init = init,
                    current_text_changed = current_text_changed,
                )
            )

        def add_custom_model_siwtch_3_card(parent):
            def widget_init(widget):
                widget.set_text(config.get("mix_translation_settings").get("model_type_3"))
                widget.set_placeholder_text("请输入模型名称 ...")

            def widget_callback(widget, text: str):
                config = self.load_config()
                config["mix_translation_settings"]["model_type_3"] = text.strip()
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
                config = self.load_config()
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