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
            "request_timeout": 120,
            "round_limit": 10,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置容器
        self.vbox = QVBoxLayout(self)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24)

        # 初始化控件引用
        self.lines_limit_card = None
        self.tokens_limit_card = None
        self.mode_combo_box = None

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

        # 根据初始模式设置可见性
        self.update_limit_cards_visibility(config)

        # 填充
        self.vbox.addStretch(1)

    def update_limit_cards_visibility(self, config):
        """根据当前模式更新限制卡片的可见性"""
        if config["lines_limit_switch"]:
            self.tokens_limit_card.hide()
            self.lines_limit_card.show()
        else:
            self.lines_limit_card.hide()
            self.tokens_limit_card.show()

    # 子任务切分模式
    def add_widget_01(self, parent, config) -> None:
        # 定义模式配对列表（显示文本, 存储值）
        mode_pairs = [
            (self.tra("行数模式"), "lines"),
            (self.tra("Token模式"), "tokens")
        ]
        
        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in mode_pairs]

        def init(widget) -> None:
            """初始化时根据配置设置当前选项"""
            current_config = self.load_config()
            
            # 根据配置确定当前模式值
            if current_config.get("lines_limit_switch", False):
                current_value = "lines"
            else:
                current_value = "tokens"
                
            # 通过存储值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时更新配置"""
            # 通过显示文本查找对应的存储值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "tokens"  # 默认值
            )
            
            config = self.load_config()
            if value == "lines":
                config["lines_limit_switch"] = True
                config["tokens_limit_switch"] = False
            else:
                config["lines_limit_switch"] = False
                config["tokens_limit_switch"] = True
                
            self.save_config(config)
            self.update_limit_cards_visibility(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, value in translated_pairs]

        self.mode_combo_box = ComboBoxCard(
            self.tra("翻译任务切分模式"),
            self.tra("选择翻译任务切分的模式"),
            options,
            init=init,
            current_text_changed=current_text_changed,
        )
        parent.addWidget(self.mode_combo_box)

    # 子任务的最大文本行数
    def add_widget_02(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("lines_limit"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["lines_limit"] = value
            self.save_config(config)

        self.lines_limit_card = SpinCard(
            self.tra("翻译任务的文本行数"),
            self.tra("当翻译任务切分模式设置为 行数模式 时，按此值对原文进行切分"),
            init=init,
            value_changed=value_changed,
        )
        parent.addWidget(self.lines_limit_card)

    # 子任务的最大 Token 数量
    def add_widget_03(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("tokens_limit"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["tokens_limit"] = value
            self.save_config(config)

        self.tokens_limit_card = SpinCard(
            self.tra("翻译任务的 Token 数量"),
            self.tra("当翻译任务切分模式设置为 Token 模式 时，按此值对原文进行切分"),
            init=init,
            value_changed=value_changed,
        )
        parent.addWidget(self.tokens_limit_card)

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
                self.tra("并发任务数"),
                self.tra("合理设置可以极大的增加翻译速度，请设置为本地模型的 np 值或者参考在线接口的官方文档，设置为 0 为自动模式"),
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
                self.tra("参考上文行数"),
                self.tra("行数不宜设置过大，建议10行以内 (不支持本地类接口)"),
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
                self.tra("请求超时时间(s)"),
                self.tra("翻译任务发起请求时等待模型回复的最长时间，超时仍未收到回复，则会判断为任务失败"),
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
                self.tra("翻译流程的最大轮次"),
                self.tra("当完成一轮翻译后，如果还有未翻译的条目，将重新开始新的翻译流程，直到翻译完成或者达到最大轮次"),
                init = init,
                value_changed = value_changed,
            )
        )