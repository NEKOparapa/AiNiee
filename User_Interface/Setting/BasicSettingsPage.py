from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from AiNieeBase import AiNieeBase
from Widget.SpinCard import SpinCard
from Widget.ComboBoxCard import ComboBoxCard

class BasicSettingsPage(QFrame, AiNieeBase):

    DEFAULT = {
        "lines_limit_switch": False,
        "tokens_limit_switch": True,
        "lines_limit": 16,
        "tokens_limit": 512,
        "pre_line_counts": 0,
        "user_thread_counts": 0,
        "retry_count_limit": 1,
        "round_limit": 8,
    }

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 载入配置文件
        config = self.load_config()

        # 设置容器
        self.vbox = QVBoxLayout(self)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_01(self.vbox, config)
        self.add_widget_02(self.vbox, config)
        self.add_widget_03(self.vbox, config)
        self.add_widget_04(self.vbox, config)
        self.add_widget_05(self.vbox, config)
        self.add_widget_06(self.vbox, config)
        self.add_widget_07(self.vbox, config)

        # 填充
        self.vbox.addStretch(1) # 确保控件顶端对齐

    # 任务切分模式
    def add_widget_01(self, parent, config):
        def init(widget):
            lines_limit_switch = config.get("lines_limit_switch")
            tokens_limit_switch = config.get("tokens_limit_switch")

            if lines_limit_switch == True and tokens_limit_switch == False:
                widget.set_current_index(0)
                
            if lines_limit_switch == False and tokens_limit_switch == True:
                widget.set_current_index(1)
            
        def current_text_changed(widget, text: str):
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
                "任务切分模式", 
                "选择翻译任务切分的模式",
                [
                    "行数模式",
                    "Token 模式",
                ],
                init = init,
                current_text_changed = current_text_changed,
            )
        )
        
    # 每次发送的最大行数
    def add_widget_02(self, parent, config):
        def init(widget):
            widget.set_range(0, 2048)
            widget.set_value(config.get("lines_limit"))

        def value_changed(widget, value: int):
            config = self.load_config()
            config["lines_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "每次发送的最大行数", 
                "当任务切分模式设置为 行数模式 时生效",
                init = init,
                value_changed = value_changed,
            )
        )

    # 每次发送的最大 Token 数
    def add_widget_03(self, parent, config):
        def init(widget):
            widget.set_range(0, 2048)
            widget.set_value(config.get("tokens_limit"))

        def value_changed(widget, value: int):
            config = self.load_config()
            config["tokens_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "每次发送的最大 Token 数", 
                "当任务切分模式设置为 Token 模式 时生效",
                init = init,
                value_changed = value_changed,
            )
        )
        
    # 参考上文行数
    def add_widget_04(self, parent, config):
        def init(widget):
            widget.set_range(0, 2048)
            widget.set_value(config.get("pre_line_counts"))

        def value_changed(widget, value: int):
            config = self.load_config()
            config["pre_line_counts"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "参考上文行数", 
                "每个任务携带的参考上文的行数（不支持 Sakura v0.9 模型）",
                init = init,
                value_changed = value_changed,
            )
        )
        
    # 并行子任务数量
    def add_widget_05(self, parent, config):
        def init(widget):
            widget.set_range(0, 2048)
            widget.set_value(config.get("user_thread_counts"))

        def value_changed(widget, value: int):
            config = self.load_config()
            config["user_thread_counts"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "并行子任务数量", 
                "合理设置可以极大的增加翻译速度，请设置为本地模型的 np 值或者参考在线接口的官方文档，设置为 0 为自动模式",
                init = init,
                value_changed = value_changed,
            )
        )
        
    # 并行子任务数量
    def add_widget_06(self, parent, config):
        def init(widget):
            widget.set_range(0, 2048)
            widget.set_value(config.get("retry_count_limit"))

        def value_changed(widget, value: int):
            config = self.load_config()
            config["retry_count_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "错误重试的最大次数", 
                "当遇到行数不匹配等翻译错误时进行重试的最大次数",
                init = init,
                value_changed = value_changed,
            )
        )
        
    # 并行子任务数量
    def add_widget_07(self, parent, config):
        def init(widget):
            widget.set_range(0, 2048)
            widget.set_value(config.get("round_limit"))

        def value_changed(widget, value: int):
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