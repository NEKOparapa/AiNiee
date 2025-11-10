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
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.ComboBoxCard import ComboBoxCard

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

        # think_switch
        if "think_switch" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_think_switch(self.vbox, config)

        # 获取接口格式以进行条件渲染
        settings = config.get("platforms").get(self.key).get("key_in_settings")
        api_format = config.get("platforms").get(self.key).get("api_format")

        # think_depth - 仅在格式为 OpenAI 或 Anthropic 时显示
        if "think_depth" in settings and api_format in ["OpenAI", "Anthropic"]:
            self.add_widget_think_depth(self.vbox, config)

        # thinking_budget - 仅在格式为 Google 时显示
        if "thinking_budget" in settings and api_format == "Google":
            self.add_widget_thinking_budget(self.vbox, config, preset)

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


    # 思考开关
    def add_widget_think_switch(self, parent, config):
        def init(widget):
            widget.set_checked(config.get("platforms").get(self.key).get("think_switch"))

        def checked_changed(widget, checked: bool):
            config = self.load_config()
            config["platforms"][self.key]["think_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("think_switch"),
                self.tra("思考模式开关"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 思考深度
    def add_widget_think_depth(self, parent, config):
        def init(widget):
            platform = config.get("platforms").get(self.key)

            widget.set_items(["low","medium","high"])
            widget.set_current_index(max(0, widget.find_text(platform.get("think_depth"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["think_depth"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("think_depth"),
                self.tra("思考深度"),
                [],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 思维预算
    def add_widget_thinking_budget(self, parent, config, preset):
        def init(widget):
            widget.set_range(-1, 32768)
            value = config.get("platforms").get(self.key).get("thinking_budget", -1)
            widget.set_text(str(value))
            widget.set_value(value)

        def value_changed(widget, value):
            widget.set_text(str(value))
            config = self.load_config()
            config["platforms"][self.key]["thinking_budget"] = value
            self.save_config(config)

        if self.key in preset.get("platforms"):
            default_value = preset.get("platforms").get(self.key).get("thinking_budget")
        else:
            default_value = -1

        info_cont = self.tra("请谨慎设置，对于目标接口，此参数的默认值为") + f" {default_value} (-1代表自动)"
        parent.addWidget(
            SliderCard(
                "thinking_budget",
                info_cont,
                init = init,
                value_changed = value_changed,
            )
        )

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
            except Exception as e:
                # 建议添加错误提示，方便调试
                print(f"[INFO] 接口保存 extra_body 参数失败: {e}")

        def init(widget):
            plain_text_edit = PlainTextEdit(self)

            extra_body = config.get("platforms").get(self.key).get("extra_body")
            
            # 只有当 extra_body 是非空字典时才显示内容
            if isinstance(extra_body, dict) and extra_body:
                plain_text_edit.setPlainText(json.dumps(extra_body, ensure_ascii=False, indent=2))
            else:
                plain_text_edit.setPlainText("")

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
