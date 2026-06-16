from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import HorizontalSeparator, SingleDirectionScrollArea

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Widget.SpinCard import SpinCard
from UserInterface.Widget.ComboBoxCard import ComboBoxCard
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard

class TaskSettingsPage(QFrame, ConfigMixin, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "lines_limit_switch": False,
            "tokens_limit_switch": True,
            "lines_limit": 20,
            "tokens_limit": 1024,
            "split_optimization_enable": True,
            "chunk_soft_limit_extra_lines": 15,
            "chunk_soft_limit_extra_tokens": 100,
            "split_optimization_mode": "dynamic",
            "retry_split_min_lines": 15,
            "retry_split_min_tokens": 100,
            "user_thread_counts": 0,
            "request_timeout": 120,
            "round_limit": 10,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)

        # 设置滚动容器
        self.scroller = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container.addWidget(self.scroller)

        # 设置容器
        self.vbox_parent = QWidget(self)
        self.vbox_parent.setStyleSheet("QWidget { background: transparent; }")
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24)
        self.scroller.setWidget(self.vbox_parent)

        # 初始化控件引用
        self.lines_limit_card = None
        self.tokens_limit_card = None
        self.split_optimization_mode_card = None
        self.chunk_soft_limit_extra_lines_card = None
        self.chunk_soft_limit_extra_tokens_card = None
        self.retry_split_min_lines_card = None
        self.retry_split_min_tokens_card = None
        self.mode_combo_box = None

        # 添加控件
        self.add_widget_01(self.vbox, config)
        self.add_widget_02(self.vbox, config)
        self.add_widget_03(self.vbox, config)
        self.add_widget_split_optimization_enable(self.vbox, config)
        self.add_widget_split_optimization_mode(self.vbox, config)
        self.add_widget_chunk_soft_limit_extra_lines(self.vbox, config)
        self.add_widget_chunk_soft_limit_extra_tokens(self.vbox, config)
        self.add_widget_retry_split_min_lines(self.vbox, config)
        self.add_widget_retry_split_min_tokens(self.vbox, config)
        self.vbox.addWidget(HorizontalSeparator())
        self.add_widget_04(self.vbox, config)
        self.vbox.addWidget(HorizontalSeparator())
        self.add_widget_request_timeout(self.vbox, config)
        self.add_widget_06(self.vbox, config)

        # 根据初始模式设置可见性
        self.update_limit_cards_visibility(config)

        # 填充
        self.vbox.addStretch(1)

    def update_limit_cards_visibility(self, config):
        """根据当前模式更新限制卡片的可见性"""
        line_mode = config["lines_limit_switch"]
        optimization_enabled = config.get("split_optimization_enable", False)

        if line_mode:
            self.tokens_limit_card.hide()
            self.lines_limit_card.show()
            self.chunk_soft_limit_extra_tokens_card.hide()
            self.retry_split_min_tokens_card.hide()
            self.chunk_soft_limit_extra_lines_card.show()
            self.retry_split_min_lines_card.show()
        else:
            self.lines_limit_card.hide()
            self.tokens_limit_card.show()
            self.chunk_soft_limit_extra_lines_card.hide()
            self.retry_split_min_lines_card.hide()
            self.chunk_soft_limit_extra_tokens_card.show()
            self.retry_split_min_tokens_card.show()

        for card in (
            self.split_optimization_mode_card,
            self.chunk_soft_limit_extra_lines_card,
            self.chunk_soft_limit_extra_tokens_card,
            self.retry_split_min_lines_card,
            self.retry_split_min_tokens_card,
        ):
            if card is not None:
                card.setEnabled(optimization_enabled)

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
            self.tra("任务切分模式"),
            self.tra("选择任务切分的模式"),
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
            self.tra("任务的文本行数"),
            self.tra("当任务切分模式设置为 行数模式 时，按此值对原文进行切分"),
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
            self.tra("任务的 Token 数量"),
            self.tra("当任务切分模式设置为 Token 模式 时，按此值对原文进行切分"),
            init=init,
            value_changed=value_changed,
        )
        parent.addWidget(self.tokens_limit_card)

    def add_widget_split_optimization_enable(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_checked(config.get("split_optimization_enable", False))

        def checked_changed(widget, checked: bool) -> None:
            config = self.load_config()
            config["split_optimization_enable"] = checked
            self.save_config(config)
            self.update_limit_cards_visibility(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("启用尾巴分割优化"),
                self.tra("开启后将按所选模式优化任务末尾过短分片，行数模式与 Token 模式都会生效"),
                init=init,
                checked_changed=checked_changed,
            )
        )

    def add_widget_split_optimization_mode(self, parent, config) -> None:
        mode_pairs = [
            (self.tra("动态分割模式"), "dynamic"),
            (self.tra("尾巴分割模式"), "tail"),
        ]
        translated_pairs = [(display, value) for display, value in mode_pairs]

        def init(widget) -> None:
            current_config = self.load_config()
            current_value = current_config.get("split_optimization_mode", "dynamic")
            if current_value not in {"dynamic", "tail"}:
                current_value = "dynamic"
            index = next((i for i, (_, value) in enumerate(translated_pairs) if value == current_value), 0)
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            value = next((value for display, value in translated_pairs if display == text), "dynamic")
            config = self.load_config()
            config["split_optimization_mode"] = value
            self.save_config(config)

        self.split_optimization_mode_card = ComboBoxCard(
            self.tra("尾巴分割模式"),
            self.tra("动态分割会尽量消除末尾小分片，尾巴分割会让最终尾巴落入软上限范围"),
            [display for display, _ in translated_pairs],
            init=init,
            current_text_changed=current_text_changed,
        )
        parent.addWidget(self.split_optimization_mode_card)

    def add_widget_chunk_soft_limit_extra_lines(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("chunk_soft_limit_extra_lines"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["chunk_soft_limit_extra_lines"] = value
            self.save_config(config)

        self.chunk_soft_limit_extra_lines_card = SpinCard(
            self.tra("小尾巴软上限(行)"),
            self.tra("行数模式下，允许末尾小分片合并到上一任务的额外行数"),
            init=init,
            value_changed=value_changed,
        )
        parent.addWidget(self.chunk_soft_limit_extra_lines_card)

    def add_widget_chunk_soft_limit_extra_tokens(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("chunk_soft_limit_extra_tokens"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["chunk_soft_limit_extra_tokens"] = value
            self.save_config(config)

        self.chunk_soft_limit_extra_tokens_card = SpinCard(
            self.tra("小尾巴软上限(Token)"),
            self.tra("Token 模式下，允许末尾小分片合并到上一任务的额外 Token 数"),
            init=init,
            value_changed=value_changed,
        )
        parent.addWidget(self.chunk_soft_limit_extra_tokens_card)

    def add_widget_retry_split_min_lines(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(1, 9999999)
            widget.set_value(config.get("retry_split_min_lines"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["retry_split_min_lines"] = value
            self.save_config(config)

        self.retry_split_min_lines_card = SpinCard(
            self.tra("重试最小切分(行)"),
            self.tra("行数模式下，多轮重试自动缩小分片时不会低于该行数"),
            init=init,
            value_changed=value_changed,
        )
        parent.addWidget(self.retry_split_min_lines_card)

    def add_widget_retry_split_min_tokens(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(1, 9999999)
            widget.set_value(config.get("retry_split_min_tokens"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["retry_split_min_tokens"] = value
            self.save_config(config)

        self.retry_split_min_tokens_card = SpinCard(
            self.tra("重试最小切分(Token)"),
            self.tra("Token 模式下，多轮重试自动缩小分片时不会低于该 Token 数"),
            init=init,
            value_changed=value_changed,
        )
        parent.addWidget(self.retry_split_min_tokens_card)

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
                self.tra("单元任务发起请求时等待模型回复的最长时间，超时仍未收到回复，则会判断为任务失败"),
                init = init,
                value_changed = value_changed,
            )
        )

    # 任务流程的最大轮次
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
                self.tra("任务流程的最大轮次"),
                self.tra("当完成一轮任务后，如果还有未翻译/润色的条目，将重新开始新的任务流程，直到翻译/润色完成或者达到最大轮次"),
                init = init,
                value_changed = value_changed,
            )
        )
