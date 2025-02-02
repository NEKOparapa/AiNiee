from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from Base.Base import Base
from Widget.SpinCard import SpinCard
from Widget.Separator import Separator
from Widget.ComboBoxCard import ComboBoxCard

class BasicSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "lines_limit_switch": False,
            "tokens_limit_switch": True,
            "lines_limit": 10,
            "tokens_limit": 384,
            "pre_line_counts": 0,
            "user_thread_counts": 0,
            "request_timeout": 90,
            "round_limit": 20,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置容器
        self.vbox = QVBoxLayout(self)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_01(self.vbox, config)
        self.add_widget_02(self.vbox, config)
        self.add_widget_03(self.vbox, config)
        self.vbox.addWidget(Separator())
        self.add_widget_04(self.vbox, config)
        self.add_widget_05(self.vbox, config)
        self.vbox.addWidget(Separator())
        self.add_widget_request_timeout(self.vbox, config)
        self.add_widget_06(self.vbox, config)

        # 填充
        self.vbox.addStretch(1) # 确保控件顶端对齐

    # 子任务切分模式
    def add_widget_01(self, parent, config) -> None:
        def init(widget) -> None:
            lines_limit_switch = config.get("lines_limit_switch")
            tokens_limit_switch = config.get("tokens_limit_switch")

            if lines_limit_switch == True and tokens_limit_switch == False:
                widget.set_current_index(0)

            if lines_limit_switch == False and tokens_limit_switch == True:
                widget.set_current_index(1)

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()

            if text == "行数模式":
                config["lines_limit_switch"] = True
                config["tokens_limit_switch"] = False

            if text == "Token 模式":
                config["lines_limit_switch"] = False
                config["tokens_limit_switch"] = True

            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                "翻译任务切分模式",
                "选择翻译任务切分的模式",
                [
                    "行数模式",
                    "Token 模式",
                ],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 子任务的最大文本行数
    def add_widget_02(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("lines_limit"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["lines_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "翻译任务的文本行数",
                "当翻译任务切分模式设置为 行数模式 时，按此值对原文进行切分",
                init = init,
                value_changed = value_changed,
            )
        )

    # 子任务的最大 Token 数量
    def add_widget_03(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("tokens_limit"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["tokens_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "翻译任务的 Token 数量",
                "当翻译任务切分模式设置为 Token 模式 时，按此值对原文进行切分",
                init = init,
                value_changed = value_changed,
            )
        )

    # 同时执行的子任务数量
    def add_widget_04(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("user_thread_counts"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["user_thread_counts"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "并发任务数",
                "合理设置可以极大的增加翻译速度，请设置为本地模型的 np 值或者参考在线接口的官方文档，设置为 0 为自动模式",
                init = init,
                value_changed = value_changed,
            )
        )

    # 每个子任务携带的参考上文行数
    def add_widget_05(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("pre_line_counts"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["pre_line_counts"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "参考上文行数",
                "启用此功能在大部分情况下可以改善长句的翻译质量，但是会降低翻译速度",
                init = init,
                value_changed = value_changed,
            )
        )

    # 请求超时时间
    def add_widget_request_timeout(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("request_timeout"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["request_timeout"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "请求超时时间（秒）",
                "翻译任务发起请求时等待模型回复的最长时间，超时仍未收到回复，则会判断为任务失败（不支持 Google 系列模型）",
                init = init,
                value_changed = value_changed,
            )
        )

    # 翻译流程的最大轮次
    def add_widget_06(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("round_limit"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["round_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "翻译流程的最大轮次",
                "当完成一轮翻译后，如果还有未翻译的条目，将重新开始新的翻译流程，直到翻译完成或者达到最大轮次",
                init = init,
                value_changed = value_changed,
            )
        )