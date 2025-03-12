import os
import json

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import HyperlinkLabel, PlainTextEdit
from qfluentwidgets import MessageBoxBase
from qfluentwidgets import SingleDirectionScrollArea

from Base.Base import Base
from Widget.SliderCard import SliderCard
from Widget.GroupCard import GroupCard

class ArgsEditPage(MessageBoxBase, Base):

    def __init__(self, window, key):
        super().__init__(window)

        # 初始化
        self.key = key

        # 设置框体
        self.widget.setFixedSize(960, 720)
        self.yesButton.setText(self.tra("关闭"))
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


        # extra_body
        if "extra_body" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_extra_body(self.vbox, config)

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



    # 自定义Body
    def add_widget_extra_body(self, parent, config):

        def text_changed(widget):
            try:
                config = self.load_config()

                extra_body_str = widget.toPlainText().strip()
                if not extra_body_str:
                    config["platforms"][self.key]["extra_body"] = {}
                else:
                    extra_body_dict = json.loads(extra_body_str.replace("'", "\""))
                    if extra_body_dict is None:
                        extra_body_dict = {}
                        
                    config["platforms"][self.key]["extra_body"] = extra_body_dict

                self.save_config(config)
            except:
                pass

        def init(widget):
            plain_text_edit = PlainTextEdit(self)

            extra_body = config.get("platforms").get(self.key).get("extra_body")
            if not extra_body:
                plain_text_edit.setPlainText("")
            else:
                plain_text_edit.setPlainText(json.dumps(extra_body))

            info_cont = self.tra("请输入自定义Body")
            plain_text_edit.setPlaceholderText(info_cont)
            plain_text_edit.textChanged.connect(lambda: text_changed(plain_text_edit))
            widget.addWidget(plain_text_edit)

        parent.addWidget(
            GroupCard(
                "extra_body",
                self.tra("请输入自定义Body，例如 {\"provider\": {\"order\": [\"DeepInfra\", \"Together\"], \"allow_fallbacks\": false}}"),
                init = init,
            )
        )


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

        info_cont = self.tra("请谨慎设置，对于目标接口，此参数的默认值为") + f" {default_value}"
        parent.addWidget(
            SliderCard(
                "top_p",
                info_cont,
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

        info_cont = self.tra("请谨慎设置，对于目标接口，此参数的默认值为") + f" {default_value}"
        parent.addWidget(
            SliderCard(
                "temperature",
                info_cont,
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

        info_cont = self.tra("请谨慎设置，对于目标接口，此参数的默认值为") + f" {default_value}"
        parent.addWidget(
            SliderCard(
                "presence_penalty",
                info_cont,
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

        info_cont = self.tra("请谨慎设置，对于目标接口，此参数的默认值为") + f" {default_value}"
        parent.addWidget(
            SliderCard(
                "frequency_penalty",
                info_cont,
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

        hyper_link_label = HyperlinkLabel(QUrl(url), self.tra("点击查看文档"))
        hyper_link_label.setUnderlineVisible(True)

        parent.addSpacing(16)
        parent.addWidget(hyper_link_label, alignment = Qt.AlignHCenter)