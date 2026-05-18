import os
import json

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import PlainTextEdit
from qfluentwidgets import MessageBoxBase
from qfluentwidgets import SingleDirectionScrollArea
from qfluentwidgets import SmoothMode

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import platform_preset_path
from ModuleFolders.Log.Log import LogMixin
from UserInterface.Widget.SliderCard import SliderCard
from UserInterface.Widget.GroupCard import GroupCard
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface.Widget.ComboBoxCard import ComboBoxCard
from UserInterface.Widget.SpinCard import SpinCard

class ArgsEditPage(MessageBoxBase, ConfigMixin, LogMixin, Base):

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
        preset = self.load_file(platform_preset_path())
        settings = config.get("platforms").get(self.key).get("key_in_settings")

        # 设置主布局
        self.viewLayout.setContentsMargins(0, 0, 0, 0)

        # 设置滚动器
        self.scroller = SingleDirectionScrollArea(self, orient = Qt.Vertical)
        # 弹窗内设置项较多，关闭平滑滚动可减少滚动动画带来的连续重绘。
        self.scroller.setSmoothMode(SmoothMode.NO_SMOOTH)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.viewLayout.addWidget(self.scroller)

        # 设置滚动控件
        self.vbox_parent = QWidget(self)
        self.vbox_parent.setObjectName("argsEditScrollWidget")
        self.vbox_parent.setStyleSheet("#argsEditScrollWidget { background: transparent; }")
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下
        self.scroller.setWidget(self.vbox_parent)


        # extra_body
        if "extra_body" in settings:
            self.add_widget_extra_body(self.vbox, config)

        # rpm_limit
        if "rpm_limit" in settings:
            self.add_widget_rpm(self.vbox, config)

        # temperature
        if "temperature" in settings:
            self.add_widget_temperature(self.vbox, config, preset)

        # think_switch
        if "think_switch" in settings:
            self.add_widget_think_switch(self.vbox, config)

        # 获取接口格式以进行条件渲染
        api_format = config.get("platforms").get(self.key).get("api_format")

        # think_depth - 仅在格式为 OpenAI 或 Anthropic 时显示
        if "think_depth" in settings and api_format in ["OpenAI", "Anthropic"]:
            self.add_widget_think_depth(self.vbox, config)

        # Google 格式的思考参数配置 - 根据模型版本互斥显示
        if api_format == "Google":
            from ModuleFolders.Infrastructure.LLMRequester.ModelConfigHelper import ModelConfigHelper

            model_name = config.get("platforms").get(self.key).get("model", "")

            if ModelConfigHelper.is_gemini_3_or_newer(model_name):
                # Gemini 3.x 使用 thinking_level
                self.add_widget_thinking_level(self.vbox, config)
            elif "thinking_budget" in settings:
                # Gemini 2.5.x 及更早版本使用 thinking_budget
                self.add_widget_thinking_budget(self.vbox, config, preset)
        # tls_switch
        api_format = config.get("platforms").get(self.key).get("api_format")
        if "tls_switch" in settings or api_format == "OpenAI":
            self.add_widget_tls_switch(self.vbox, config)

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


    # TLS指纹模拟开关
    def add_widget_tls_switch(self, parent, config):
        def init(widget):
            widget.set_checked(config.get("platforms").get(self.key).get("tls_switch", False))

        def checked_changed(widget, checked: bool):
            config = self.load_config()
            config["platforms"][self.key]["tls_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("TLS 指纹模拟"),
                self.tra("开启后使用浏览器 TLS 指纹请求 OpenAI 兼容接口，并自动应用系统代理"),
                init = init,
                checked_changed = checked_changed,
            )
        )

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
                self.tra("思考模式"),
                self.tra("开启后按当前平台规则附加模型思考参数，不支持的模型会保持默认请求"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 思考深度
    def add_widget_think_depth(self, parent, config):
        def init(widget):
            platform = config.get("platforms").get(self.key)

            widget.set_items(["low","medium","high","xhigh"])
            widget.set_current_index(max(0, widget.find_text(platform.get("think_depth"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["think_depth"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("思考强度"),
                self.tra("调整模型的思考强度等级"),
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

        info_cont = self.tra("Gemini 2.5 等模型的思考 Token 预算，-1 表示自动；默认值为") + f" {default_value}"
        parent.addWidget(
            SliderCard(
                self.tra("思考预算"),
                info_cont,
                init = init,
                value_changed = value_changed,
            )
        )

    # 思考深度级别 (Gemini 3 专用)
    def add_widget_thinking_level(self, parent, config):
        from ModuleFolders.Infrastructure.LLMRequester.ModelConfigHelper import ModelConfigHelper

        def init(widget):
            platform = config.get("platforms").get(self.key)
            model_name = platform.get("model", "")

            # 根据模型类型设置可用选项
            items = ModelConfigHelper.get_thinking_level_options(model_name)
            widget.set_items(items)

            current = platform.get("thinking_level", "high")
            idx = widget.find_text(current)
            widget.set_current_index(max(0, idx if idx >= 0 else len(items) - 1))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["thinking_level"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("思考级别"),
                self.tra("Gemini 3 专用，Pro 模型仅支持 low 和 high"),
                [],
                init=init,
                current_text_changed=current_text_changed,
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

            info_cont = self.tra("请输入extra_body额外请求参数 JSON")
            plain_text_edit.setPlaceholderText(info_cont)
            plain_text_edit.textChanged.connect(lambda: text_changed(plain_text_edit))
            widget.addWidget(plain_text_edit)

        parent.addWidget(
            GroupCard(
                self.tra("自定义请求体"),
                self.tra("填写会合并到请求体的额外 JSON 参数，适合高级接口选项"),
                init = init,
            )
        )

    # 每分钟请求数
    def add_widget_rpm(self, parent, config):
        def init(widget):
            widget.set_range(0, 9999999)
            widget.set_value(config.get("platforms").get(self.key).get("rpm_limit", 4096))

        def value_changed(widget, value: str):
            config = self.load_config()
            config["platforms"][self.key]["rpm_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                self.tra("每分钟请求数"),
                self.tra("限制该接口每分钟最多发送的请求数量（RPM）"),
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

        info_cont = self.tra("控制回复随机性，值越高输出越发散；默认值为") + f" {default_value}"
        parent.addWidget(
            SliderCard(
                self.tra("温度"),
                info_cont,
                init = init,
                value_changed = value_changed,
            )
        )
