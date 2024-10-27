import os
import json

from PyQt5.Qt import Qt
from PyQt5.Qt import QUrl
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import HyperlinkLabel
from qfluentwidgets import MessageBoxBase
from qfluentwidgets import SingleDirectionScrollArea

from Base.Base import Base
from Widget.SliderCard import SliderCard

class ArgsEditPage(MessageBoxBase, Base):

    DEFAULT = {}

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
        preset = self.load_file("./Resource/platforms/preset.json")

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

        # top_p
        if "top_p" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_top_p(self.vbox, config, preset)

        # temperature
        if "temperature" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_temperature(self.vbox, config, preset)

        # presence_penalty
        if "presence_penalty" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_presence_penalty(self.vbox, config, preset)

        # frequency_penalty
        if "frequency_penalty" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_frequency_penalty(self.vbox, config, preset)

        # 添加链接
        self.add_widget_url(self.vbox, config, preset)

        # 填充
        self.vbox.addStretch(1)

    # 从文件加载
    def load_file(self, path: str) -> dict:
        result = {}

        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                result = json.load(reader)
        else:
            self.error(f"未找到 {path} 文件 ...")

        return result

    # top_p
    def add_widget_top_p(self, parent, config, preset):
        def init(widget):
            widget.set_range(0, 100)
            widget.set_text(f"{config.get("platforms").get(self.key).get("top_p"):.2f}")
            widget.set_value(int(config.get("platforms").get(self.key).get("top_p") * 100))

        def value_changed(widget, value):
            widget.set_text(f"{(value / 100):.2f}")

            config = self.load_config()
            config["platforms"][self.key]["top_p"] = value / 100
            self.save_config(config)

        if self.key in preset.get("platforms"):
            default_value = preset.get("platforms").get(self.key).get("top_p")
        else:
            default_value = preset.get("platforms").get("openai").get("top_p")

        parent.addWidget(
            SliderCard(
                "top_p",
                f"请谨慎设置，错误的值可能导致结果异常或者请求报错，对于目标接口，此参数的默认值为 {default_value}",
                init = init,
                value_changed = value_changed,
            )
        )

    # temperature
    def add_widget_temperature(self, parent, config, preset):
        def init(widget):
            widget.set_range(0, 200)
            widget.set_text(f"{config.get("platforms").get(self.key).get("temperature"):.2f}")
            widget.set_value(int(config.get("platforms").get(self.key).get("temperature") * 100))

        def value_changed(widget, value):
            widget.set_text(f"{(value / 100):.2f}")

            config = self.load_config()
            config["platforms"][self.key]["temperature"] = value / 100
            self.save_config(config)

        if self.key in preset.get("platforms"):
            default_value = preset.get("platforms").get(self.key).get("temperature")
        else:
            default_value = preset.get("platforms").get("openai").get("temperature")

        parent.addWidget(
            SliderCard(
                "temperature",
                f"请谨慎设置，错误的值可能导致结果异常或者请求报错，对于目标接口，此参数的默认值为 {default_value}",
                init = init,
                value_changed = value_changed,
            )
        )

    # presence_penalty
    def add_widget_presence_penalty(self, parent, config, preset):
        def init(widget):
            widget.set_range(-200, 200)
            widget.set_text(f"{config.get("platforms").get(self.key).get("presence_penalty"):.2f}")
            widget.set_value(int(config.get("platforms").get(self.key).get("presence_penalty") * 100))

        def value_changed(widget, value):
            widget.set_text(f"{(value / 100):.2f}")

            config = self.load_config()
            config["platforms"][self.key]["presence_penalty"] = value / 100
            self.save_config(config)

        if self.key in preset.get("platforms"):
            default_value = preset.get("platforms").get(self.key).get("presence_penalty")
        else:
            default_value = preset.get("platforms").get("openai").get("presence_penalty")

        parent.addWidget(
            SliderCard(
                "presence_penalty",
                f"请谨慎设置，错误的值可能导致结果异常或者请求报错，对于目标接口，此参数的默认值为 {default_value}",
                init = init,
                value_changed = value_changed,
            )
        )

    # frequency_penalty
    def add_widget_frequency_penalty(self, parent, config, preset):
        def init(widget):
            widget.set_range(-200, 200)
            widget.set_text(f"{config.get("platforms").get(self.key).get("frequency_penalty"):.2f}")
            widget.set_value(int(config.get("platforms").get(self.key).get("frequency_penalty") * 100))

        def value_changed(widget, value):
            widget.set_text(f"{(value / 100):.2f}")

            config = self.load_config()
            config["platforms"][self.key]["frequency_penalty"] = value / 100
            self.save_config(config)

        if self.key in preset.get("platforms"):
            default_value = preset.get("platforms").get(self.key).get("frequency_penalty")
        else:
            default_value = preset.get("platforms").get("openai").get("frequency_penalty")

        parent.addWidget(
            SliderCard(
                "frequency_penalty",
                f"请谨慎设置，错误的值可能导致结果异常或者请求报错，对于目标接口，此参数的默认值为 {default_value}",
                init = init,
                value_changed = value_changed,
            )
        )

    # 添加链接
    def add_widget_url(self, parent, config, preset):
        url = "https://platform.openai.com/docs/api-reference/chat/create"

        if self.key == "cohere":
            url = "https://docs.cohere.com/reference/chat"

        if self.key == "google":
            url = "https://ai.google.dev/api/generate-content"

        if self.key == "sakura":
            url = "https://github.com/SakuraLLM/SakuraLLM#%E6%8E%A8%E7%90%86"

        if self.key == "deepseek":
            url = "https://api-docs.deepseek.com/zh-cn/quick_start/parameter_settings"

        if self.key == "anthropic":
            url = "https://docs.anthropic.com/en/api/getting-started"

        hyper_link_label = HyperlinkLabel(QUrl(url), "点击查看文档")
        hyper_link_label.setUnderlineVisible(True)

        parent.addSpacing(16)
        parent.addWidget(hyper_link_label, alignment = Qt.AlignHCenter)