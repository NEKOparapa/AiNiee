
import os
import json
import copy
import random
from functools import partial

from rich import print
from PyQt5.Qt import Qt
from PyQt5.Qt import QEvent
from PyQt5.Qt import QTimer
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import InfoBar
from qfluentwidgets import InfoBarPosition
from qfluentwidgets import RoundMenu
from qfluentwidgets import FluentIcon
from qfluentwidgets import PrimaryPushButton
from qfluentwidgets import PrimaryDropDownPushButton

from Widget.FlowCard import FlowCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.APIEditMessageBox import APIEditMessageBox
from Widget.LineEditMessageBox import LineEditMessageBox

class PlatformPage(QFrame):

    CUSTOM = {
        "tag": "",
        "group": "custom",
        "name": "",
        "api_url": "",
        "api_key": "",
        "api_format": "",
        "model": "",
        "proxy": "",
        "account": "",
        "auto_complete": True,
        "model_datas": [
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-sonnet-20240620",
        ],
        "format_datas": [
            "OpenAI",
            "Anthropic",
        ],
        "account_datas": {},
        "key_in_settings": [
            "api_url",
            "api_key",
            "api_format",
            "model",
            "proxy",
            "auto_complete",
        ],
    }

    DEFAULT = {}

    def __init__(self, text: str, window, configurator, background_executor):
        super().__init__(parent = window)

        self.setObjectName(text.replace(" ", "-"))
        self.window = window
        self.configurator = configurator
        self.background_executor = background_executor

        # 加载默认配置
        self.DEFAULT = self.load_file(os.path.join(self.configurator.resource_dir, "platforms.json"))
    
        # 载入配置文件
        config = self.load_config()
        config = self.save_config(config)

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_head_widget(self.container, config)
        self.add_body_widget(self.container, config)
        self.add_foot_widget(self.container, config)

        # 填充
        self.container.addStretch(1)

    # 从文件加载
    def load_file(self, path: str) -> dict:
        result = {}

        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                result = json.load(reader)

        return result

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

    # 执行接口测试
    def api_test(self, tag: str):
        # 载入配置文件
        config = self.load_config()
        platform = config.get("platforms").get(tag)

        if self.background_executor.Request_test_switch(self):
            def on_api_test_done(result):
                if result == True:
                    InfoBar.success(
                        title = "",
                        content = "接口测试成功 ...",
                        parent = self,
                        duration = 2500,
                        orient = Qt.Horizontal,
                        position = InfoBarPosition.TOP,
                        isClosable = True,
                    )
                else:
                    InfoBar.error(
                        title = "",
                        content = "接口测试失败 ...",
                        parent = self,
                        duration = 2500,
                        orient = Qt.Horizontal,
                        position = InfoBarPosition.TOP,
                        isClosable = True,
                    )
                    
            self.background_executor(
                "接口测试",
                "",
                "",
                platform.get("tag"),
                platform.get("api_url"),
                platform.get("model"),
                platform.get("api_key"),
                platform.get("proxy"),
                platform.get("api_format"),
                on_api_test_done,
            ).start()
        else:
            InfoBar.warning(
                title = "",
                content = "接口测试正在执行中，请稍后再试 ...",
                parent = self,
                duration = 2500,
                orient = Qt.Horizontal,
                position = InfoBarPosition.TOP,
                isClosable = True,
            )

    # 删除平台
    def delete_platform(self, tag: str) -> None:
        # 载入配置文件
        config = self.load_config()
        
        # 删除对应的平台
        del config["platforms"][tag]

        # 保存配置文件
        self.save_config(config)

        # 更新控件
        self.update_custom_platform_widgets(self.flow_card)

    # 生成 UI 描述数据
    def generate_ui_datas(self, platforms: dict, is_custom: bool) -> list:
        ui_datas = []
        
        for k, v in platforms.items():
            if not is_custom:
                ui_datas.append(
                    {
                        "name": v.get("name"),
                        "menus": [
                            (
                                FluentIcon.EDIT,
                                "编辑接口",
                                partial(self.show_api_edit_message_box, k),
                            ),
                            (
                                FluentIcon.SEND,
                                "测试接口",
                                partial(self.api_test, k),
                            ),
                        ],
                    },
                )
            else:
                ui_datas.append(
                    {
                        "name": v.get("name"),
                        "menus": [
                            (
                                FluentIcon.EDIT,
                                "编辑接口",
                                partial(self.show_api_edit_message_box, k),
                            ),
                            (
                                FluentIcon.SEND,
                                "测试接口",
                                partial(self.api_test, k),
                            ),
                            (
                                FluentIcon.DELETE,
                                "删除接口",
                                partial(self.delete_platform, k),
                            ),
                        ],
                    },
                )

        return ui_datas

    # 显示 API 编辑对话框
    def show_api_edit_message_box(self, key: str):
        api_edit_message_box = APIEditMessageBox(self.window, self.configurator, key)
        api_edit_message_box.exec()

    # 初始化下拉按钮
    def init_drop_down_push_button(self, widget, datas):
        for item in datas:
            drop_down_push_button = PrimaryDropDownPushButton(item.get("name"))
            drop_down_push_button.setFixedWidth(192)
            drop_down_push_button.setContentsMargins(4, 0, 4, 0) # 左、上、右、下
            widget.add_widget(drop_down_push_button)

            menu = RoundMenu(drop_down_push_button)
            for k, v in enumerate(item.get("menus")):
                menu.addAction(
                    Action(
                        v[0],
                        v[1],
                        triggered = v[2],
                    )
                )

                # 最后一个菜单不加分割线
                menu.addSeparator() if k != len(item.get("menus")) - 1 else None
            drop_down_push_button.setMenu(menu)

    # 更新自定义平台控件
    def update_custom_platform_widgets(self, widget):
        config = self.load_config()
        platforms = {k:v for k, v in config.get("platforms").items() if v.get("group") == "custom"}

        widget.take_all_widgets()
        self.init_drop_down_push_button(
            widget,
            self.generate_ui_datas(platforms, True)
        )

    # 添加头部
    def add_head_widget(self, parent, config):
        platforms = {k:v for k, v in config.get("platforms").items() if v.get("group") == "local"}
        parent.addWidget(
            FlowCard(
                "本地接口", 
                "管理应用内置的本地大语言模型的接口信息",
                init = lambda widget: self.init_drop_down_push_button(
                    widget,
                    self.generate_ui_datas(platforms, False),
                ),
            )
        )

    # 添加主体
    def add_body_widget(self, parent, config):
        platforms = {k:v for k, v in config.get("platforms").items() if v.get("group") == "online"}
        parent.addWidget(
            FlowCard(
                "在线接口", 
                "管理应用内置的主流大语言模型的接口信息",
                init = lambda widget: self.init_drop_down_push_button(
                    widget,
                    self.generate_ui_datas(platforms, False),
                ),
            )
        )

    # 添加底部
    def add_foot_widget(self, parent, config):

        def message_box_close(widget, text: str):
            config = self.load_config()
            
            # 生成一个随机 TAG
            tag = f"custom_platform_{random.randint(100000, 999999)}"

            # 修改和保存配置
            platform = copy.deepcopy(self.CUSTOM)
            platform["tag"] = tag
            platform["name"] = text.strip()
            config["platforms"][tag] = platform
            self.save_config(config)

            # 更新UI
            self.update_custom_platform_widgets(self.flow_card)

        def on_add_button_clicked(widget):
            message_box = LineEditMessageBox(
                self.window,
                "请输入新的接口名称 ...",
                message_box_close = message_box_close
            )
            
            message_box.exec()

        def init(widget):
            # 添加新增按钮
            add_button = PrimaryPushButton("新增")
            add_button.setIcon(FluentIcon.ADD_TO)
            add_button.setContentsMargins(4, 0, 4, 0)
            add_button.clicked.connect(lambda: on_add_button_clicked(self))
            widget.add_widget_to_head(add_button)

            # 更新控件
            self.update_custom_platform_widgets(widget)

        self.flow_card = FlowCard(
            "自定义接口", 
            "在此添加和管理任何符合 OpenAI 格式或者 Anthropic 格式的大语言模型的接口信息",
            init = init,
        )
        parent.addWidget(self.flow_card)