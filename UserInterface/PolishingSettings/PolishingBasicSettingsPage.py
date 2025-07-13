from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import HorizontalSeparator

from Base.Base import Base
from Widget.SpinCard import SpinCard
from Widget.ComboBoxCard import ComboBoxCard

class PolishingBasicSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "polishing_mode_selection": "translated_text_polish",
            "polishing_pre_line_counts": 0,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_polishing_mode(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_pre_line(self.container, config)
        # 填充
        self.container.addStretch(1)

    # 页面每次展示时触发
    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self.show_event(self, event) if hasattr(self, "show_event") else None

    # 润色模式
    def add_widget_polishing_mode(self, parent, config) -> None:
        # 定义模式配对列表（显示文本, 存储值）
        mode_pairs = [
            (self.tra("原文"), "source_text_polish"),
            (self.tra("译文"), "translated_text_polish")
        ]
        
        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in mode_pairs]

        def init(widget) -> None:
            current_config = self.load_config()
            
            # 根据配置确定当前模式值
            if current_config.get("polishing_mode_selection", "") == "translated_text_polish":
                current_value = "translated_text_polish"
            else:
                current_value = "source_text_polish"
                
            # 通过存储值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            # 通过显示文本查找对应的存储值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "translated_text_polish"  # 默认值
            )
            
            config = self.load_config()
            if value == "translated_text_polish":
                config["polishing_mode_selection"] = "translated_text_polish"
            else:
                config["polishing_mode_selection"] = "source_text_polish"
                
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, value in translated_pairs]

        self.mode_combo_box = ComboBoxCard(
            self.tra("润色模式选择"),
            self.tra("选择需要润色的文本范围\n选择【原文】将润色原文文本，原文不需要翻译情况下使用\n选择【译文】将润色译文文本，在原文翻译完成后再使用"),
            options,
            init=init,
            current_text_changed=current_text_changed,
        )
        parent.addWidget(self.mode_combo_box)


    # 参考上文行数
    def add_widget_pre_line(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("polishing_pre_line_counts"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["polishing_pre_line_counts"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                self.tra("参考上文行数"),
                self.tra("行数不宜设置过大，建议10行以内"),
                init = init,
                value_changed = value_changed,
            )
        )
