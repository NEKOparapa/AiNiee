import os
import json
import copy
import random
from functools import partial

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action
from qfluentwidgets import RoundMenu
from qfluentwidgets import FluentIcon
from qfluentwidgets import PushButton
from qfluentwidgets import PrimaryDropDownPushButton

from Base.Base import Base
from Widget.FlowCard import FlowCard
from Widget.LineEditMessageBox import LineEditMessageBox
from User_Interface.Project.APIEditPage import APIEditPage
from User_Interface.Project.ArgsEditPage import ArgsEditPage
from User_Interface.Project.LimitEditPage import LimitEditPage

class PlatformPage(QFrame, Base):
    
    # 自定义平台默认配置
    CUSTOM = {
        "tag": "",
        "group": "custom",
        "name": "",
        "api_url": "https://api.lingyiwanwu.com/v1",
        "api_key": "",
        "api_format": "OpenAI",
        "rpm_limit": 4096,
        "tpm_limit": 8000000,
        "token_limit": 8000,
        "model": "gpt-4o",
        "top_p": 1.0,
        "temperature": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "account": "免费账号",
        "auto_complete": True,
        "model_datas": [
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
            "rpm_limit",
            "tpm_limit",
            "token_limit",
            "model",
            "auto_complete",
            "top_p",
            "temperature",
            "presence_penalty",
            "frequency_penalty",
        ],
    }

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 全局变量
        self.window = window

        # 加载并更新预设配置
        self.load_preset()

        # 载入配置文件
        config = self.load_config()

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

        # 完成事件
        self.subscribe(Base.EVENT.API_TEST_DONE, self.api_test_done)

    # 从文件加载
    def load_file(self, path: str) -> dict:
        result = {}

        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                result = json.load(reader)
        else:
            self.error(f"未找到 {path} 文件 ...")

        return result

    # 执行接口测试
    def api_test(self, tag: str):
        # 载入配置文件
        config = self.load_config()
        platform = config.get("platforms").get(tag)
        if Base.work_status == Base.STATUS.IDLE:
            # 更新运行状态
            Base.work_status = Base.STATUS.API_TEST

            # 创建事件参数
            data = copy.deepcopy(platform)
            data["proxy_url"] = config.get("proxy_url")
            data["proxy_enable"] = config.get("proxy_enable")

            # 触发事件
            self.emit(Base.EVENT.API_TEST_START, data)
        else:
            self.warning_toast("", "接口测试正在执行中，请稍后再试 ...")

    # 接口测试完成
    def api_test_done(self, event: int, data: dict):
        # 更新运行状态
        Base.work_status = Base.STATUS.IDLE

        if len(data.get("failure", [])) > 0:
            self.error_toast("", f"接口测试结果：成功 {len(data.get("success", []))} 个，失败 {len(data.get("failure", []))} 个 ...")
        else:
            self.success_toast("", f"接口测试结果：成功 {len(data.get("success", []))} 个，失败 {len(data.get("failure", []))} 个 ...")

    # 加载并更新预设配置
    def load_preset(self):
        # 这个函数的主要目的是保证可以通过预设文件对内置的接口的固定属性进行更新
        preset = self.load_file("./Resource/platforms/preset.json")
        config = self.load_config()

        # 从配置文件中非自定义读取接口信息数据并使用预设数据更新
        p_platforms = preset.get("platforms", {})
        c_platforms = config.get("platforms", {})
        # 遍历预设数据中的接口信息
        for k, p_platform in p_platforms.items():
            # 在配置数据中查找相同的接口
            if k in c_platforms:
                c_platform = c_platforms.get(k, {})
                # 如果该字段属于用户自定义字段，且配置数据中该字段的值合法，则使用此值更新预设数据
                for setting in p_platform.get("key_in_settings", []):
                    if c_platform.get(setting, None) != None:
                        p_platform[setting] = c_platform.get(setting, None)

        # 从配置文件中读取自定义接口信息数据并使用预设数据更新
        custom = {k: v for k, v in config.get("platforms", {}).items() if v.get("group") == "custom"}
        # 遍历自定义模型数据
        for _, platform in custom.items():
            for k, v in self.CUSTOM.items():
                # 如果该字段的值不合法，则使用预设数据更新该字段的值
                if platform.get(k, None) == None:
                    platform[k] = v

                # 如果字段不属于用户自定义字段，且不在保护字段范围内，则使用预设数据更新该字段的值
                # 模型数据除外
                if k not in self.CUSTOM.get("key_in_settings", []) and k not in ("tag", "name", "group", "model_datas"):
                    platform[k] = v

        # 汇总数据并更新配置数据中的接口信息
        platforms = {}
        platforms.update(preset.get("platforms", {}))
        platforms.update(custom)
        config["platforms"] = platforms

        # 保存并返回
        return self.save_config(config)

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

    def rename_platform(self, tag: str):
        """重命名方法"""
        def save_new_name(text: str):
            if text.strip():
                config = self.load_config()
                config["platforms"][tag]["name"] = text.strip()
                self.save_config(config)
                # 更新显示
                self.update_custom_platform_widgets(self.flow_card)
                self.success_toast("", "接口重命名成功✅")

        # 弹出输入对话框
        message_box = LineEditMessageBox(
            self.window,
            "请输入新的接口名称...",
            message_box_close=lambda widget, text: save_new_name(text)
        )
        message_box.line_edit.setText(self.load_config()["platforms"][tag]["name"])
        message_box.exec()

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
                                partial(self.show_api_edit_page, k),
                            ),
                            (
                                FluentIcon.DEVELOPER_TOOLS,
                                "编辑参数",
                                partial(self.show_args_edit_page, k),
                            ),
                            # (
                            #     FluentIcon.SCROLL,
                            #     "编辑限速",
                            #     partial(self.show_limit_edit_page, k),
                            # ),
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
                                partial(self.show_api_edit_page, k),
                            ),
                            (
                                FluentIcon.SCROLL,
                                "编辑限速",
                                partial(self.show_limit_edit_page, k),
                            ),
                            (
                                FluentIcon.DEVELOPER_TOOLS,
                                "编辑参数",
                                partial(self.show_args_edit_page, k),
                            ),
                            (
                                FluentIcon.SEND,
                                "测试接口",
                                partial(self.api_test, k),
                            ),
                            (
                                FluentIcon.LABEL,
                                "重命名",
                                partial(self.rename_platform, k),  # 新增重命名方法
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

    # 显示编辑接口对话框
    def show_api_edit_page(self, key: str):
        APIEditPage(self.window, key).exec()

    # 显示编辑参数对话框
    def show_args_edit_page(self, key: str):
        ArgsEditPage(self.window, key).exec()

    # 显示编辑限额对话框
    def show_limit_edit_page(self, key: str):
        LimitEditPage(self.window, key).exec()

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

    # 添加头部-本地接口
    def add_head_widget(self, parent, config):
        def init(widget):
            # 添加按钮
            help_button = PushButton("教程")
            help_button.setIcon(FluentIcon.HELP)
            help_button.setContentsMargins(4, 0, 4, 0)
            help_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/neavo/SakuraLLMServer")))
            widget.add_widget_to_head(help_button)

            # 更新子控件
            self.init_drop_down_push_button(
                widget,
                self.generate_ui_datas(platforms, False),
            )

        platforms = {k:v for k, v in config.get("platforms").items() if v.get("group") == "local"}
        parent.addWidget(
            FlowCard(
                "本地接口",
                "管理应用内置的本地大语言模型的接口信息",
                init = init,
            )
        )

    # 添加主体-在线接口
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

    # 添加底部-自定义接口
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
            add_button = PushButton("新增")
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