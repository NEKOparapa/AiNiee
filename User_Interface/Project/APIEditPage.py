from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

import cohere
import anthropic
import google.generativeai as genai
from openai import OpenAI

from qfluentwidgets import PlainTextEdit
from qfluentwidgets import MessageBoxBase
from qfluentwidgets import SingleDirectionScrollArea
from qfluentwidgets import PushButton, InfoBar, InfoBarPosition

from Base.Base import Base
from Widget.GroupCard import GroupCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.LineEditCard import LineEditCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.EditableComboBoxCard import EditableComboBoxCard
from Module_Folders.Request_Tester.Request import Request_Tester

class APIEditPage(MessageBoxBase, Base):

    def __init__(self, window, key):
        super().__init__(window)

        # 初始化
        self.key = key

        # 设置框体
        self.widget.setFixedSize(960, 720)
        self.yesButton.setText("关闭")
        self.cancelButton.hide()

        # 载入配置文件
        config = self.load_config()

        # 设置主布局
        self.viewLayout.setContentsMargins(0, 0, 0, 0)

        # 设置滚动器
        self.scroller = SingleDirectionScrollArea(self, orient = Qt.Vertical)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.viewLayout.addWidget(self.scroller)

        # 设置滚动控件
        self.vbox_parent = QWidget(self)
        self.vbox_parent.setStyleSheet("QWidget { background: transparent; }")
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下
        self.scroller.setWidget(self.vbox_parent)

        # 接口地址
        if "api_url" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_url(self.vbox, config)

        # 接口地址自动补全
        if "auto_complete" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_auto_complete(self.vbox, config)

        # 接口密钥
        if "api_key" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_key(self.vbox, config)

        # 接口格式
        if "api_format" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_format(self.vbox, config)

        # 账户类型
        if "account" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_account(self.vbox, config)

        # 模型名称
        if "model" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_model(self.vbox, config)

        # 填充
        self.vbox.addStretch(1)

    # 接口地址
    def add_widget_url(self, parent, config):
        def init(widget):
            widget.set_text(config.get("platforms").get(self.key).get("api_url"))
            widget.set_fixed_width(256)
            widget.set_placeholder_text("请输入接口地址 ...")

        def text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["api_url"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                "接口地址",
                "请输入接口地址，例如 https://api.deepseek.com",
                init = init,
                text_changed = text_changed,
            )
        )

    # 接口地址自动补全
    def add_widget_auto_complete(self, parent, config):
        def init(widget):
            widget.set_checked(config.get("platforms").get(self.key).get("auto_complete"))

        def checked_changed(widget, checked: bool):
            config = self.load_config()
            config["platforms"][self.key]["auto_complete"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "接口地址自动补全",
                "将自动为你填写接口地址，例如 https://api.deepseek.com -> https://api.deepseek.com/v1",
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 接口密钥
    def add_widget_key(self, parent, config):

        def text_changed(widget):
            config = self.load_config()
            config["platforms"][self.key]["api_key"] = widget.toPlainText().strip()
            self.save_config(config)

        def init(widget):
            plain_text_edit = PlainTextEdit(self)
            plain_text_edit.setPlainText(config.get("platforms").get(self.key).get("api_key"))
            plain_text_edit.setPlaceholderText("请输入接口密钥 ...")
            plain_text_edit.textChanged.connect(lambda: text_changed(plain_text_edit))
            widget.addWidget(plain_text_edit)

        parent.addWidget(
            GroupCard(
                "接口密钥",
                "请输入接口密钥，例如 sk-d0daba12345678fd8eb7b8d31c123456，多个密钥之间请使用半角逗号（,）分隔",
                init = init,
            )
        )

    # 接口格式
    def add_widget_format(self, parent, config):
        def init(widget):
            platform = config.get("platforms").get(self.key)

            widget.set_items(platform.get("format_datas"))
            widget.set_current_index(max(0, widget.find_text(platform.get("api_format"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["api_format"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "接口格式",
                "请选择接口格式，大部分模型使用 OpenAI 格式，部分中转站的 Claude 模型则使用 Anthropic 格式",
                [],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 账户类型
    def add_widget_account(self, parent, config):
        def init(widget):
            platform = config.get("platforms").get(self.key)

            widget.set_items(platform.get("account_datas"))
            widget.set_current_index(max(0, widget.find_text(platform.get("account"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["account"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "账户类型",
                "请选择账户类型",
                [],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 更新模型列表
    def update_model_list(self, widget):
        try:
            config = self.load_config()
            platforms_config = config.get("platforms").get(self.key)
            api_url = platforms_config.get("api_url")
            api_key = platforms_config.get("api_key")
            api_format = platforms_config.get("api_format")
            
            if not api_key or (self.key.startswith("custom") and not api_url):
                InfoBar.error(
                    title = '错误',
                    content = "请先填写接口地址或密钥",
                    orient = Qt.Horizontal,
                    isClosable = True,
                    position = InfoBarPosition.TOP,
                    duration = 2000,
                    parent = self
                )
                return
            # 获取模型列表
            models = self.get_models(self.key, api_url, api_key, api_format)
            
            if models:
                # 更新配置文件中的模型列表
                config["platforms"][self.key]["model_datas"] = models
                self.save_config(config)
                
                # 如果当前选中的模型不在新列表中，将其添加到列表中
                current_model = config["platforms"][self.key]["model"]
                if current_model and current_model not in models:
                    models.append(current_model)
                # 更新列表显示
                widget.combo_box.clear()
                widget.set_items(models)
                widget.set_current_index(max(0, widget.find_text(current_model)))
                
                InfoBar.success(
                    title = '成功',
                    content = "模型名称列表已更新",
                    orient = Qt.Horizontal,
                    isClosable = True,
                    position = InfoBarPosition.TOP,
                    duration = 2000,
                    parent = self
                )
            else:
                InfoBar.warning(
                    title = '警告',
                    content = "未获取到任何模型",
                    orient = Qt.Horizontal,
                    isClosable = True,
                    position = InfoBarPosition.TOP,
                    duration = 2000,
                    parent = self
                )
            
        except Exception as e:
            InfoBar.error(
                title = '错误',
                content = f"更新失败: {str(e)}",
                orient = Qt.Horizontal,
                isClosable = True,
                position = InfoBarPosition.TOP,
                duration = 2000,
                parent = self
            )

    # 获取模型列表
    def get_models(self, tag: str, api_url: str, api_key: str, api_format: str):
        try:
            # 根据不同API获取模型列表
            if tag == "cohere":
                client = cohere.Client(
                    api_key = api_key if api_key != "" else "no_key_required",
                    base_url = api_url
                )
                return [model.id for model in client.list_models()]
            
            elif tag == "google":
                genai.configure(
                    api_key = api_key if api_key != "" else "no_key_required",
                    transport = "rest"
                )
                return [model.name for model in genai.list_models()]
            
            elif tag == "anthropic" or (tag.startswith("custom_platform_") and api_format == "Anthropic"):
                client = anthropic.Anthropic(
                    api_key = api_key if api_key != "" else "no_key_required",
                    base_url = api_url
                )
                return [model.id for model in client.models.list()]
            
            else:
                client = OpenAI(
                    api_key = api_key if api_key != "" else "no_key_required",
                    base_url = api_url
                )
                return [model.id for model in client.models.list()]

        except Exception as e:
            self.error(f"获取模型列表失败: {str(e)}")
            return []

    # 模型名称
    def add_widget_model(self, parent, config):
        def init(widget):
            platforms = config.get("platforms").get(self.key)

            widget.button.clicked.connect(lambda: self.update_model_list(widget))

            # 如果默认模型列表中不存在该条目，则添加
            items = platforms.get("model_datas")
            if platforms.get("model") != "" and platforms.get("model") not in platforms.get("model_datas"):
                items.append(platforms.get("model"))

            widget.set_items(items)
            widget.set_fixed_width(256)
            widget.set_current_index(max(0, widget.find_text(platforms.get("model"))))
            widget.set_placeholder_text("请输入模型名称 ...")

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["model"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            EditableComboBoxCard(
                "模型名称",
                "请选择或者输入要使用的模型的名称",
                [],
                init = init,
                current_text_changed = current_text_changed,
                button = '⟳',
            )
        )