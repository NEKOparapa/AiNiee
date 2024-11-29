from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import MessageBoxBase
from qfluentwidgets import SingleDirectionScrollArea

from Base.Base import Base
from Widget.SpinCard import SpinCard

class LimitEditPage(MessageBoxBase, Base):

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

        # 添加控件
        self.add_widget_rpm(self.vbox, config)
        self.add_widget_tpm(self.vbox, config)
        self.add_widget_token(self.vbox, config)

        # 填充
        self.vbox.addStretch(1)

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
                "每分钟请求数",
                "RPM，即每个密钥在一分钟内能响应的请求的最大数量",
                init = init,
                value_changed = value_changed,
            )
        )

    # 每分钟 Token 数
    def add_widget_tpm(self, parent, config):
        def init(widget):
            widget.set_range(0, 9999999)
            widget.set_value(config.get("platforms").get(self.key).get("tpm_limit", 4096000))

        def value_changed(widget, value: str):
            config = self.load_config()
            config["platforms"][self.key]["tpm_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "每分钟 Token 数",
                "RPM，即每个密钥在一分钟内能生成的 Token 的最大数量",
                init = init,
                value_changed = value_changed,
            )
        )

    # 最大 Token 长度
    def add_widget_token(self, parent, config):
        def init(widget):
            widget.set_range(0, 9999999)
            widget.set_value(config.get("platforms").get(self.key).get("token_limit", 4096))

        def value_changed(widget, value: str):
            config = self.load_config()
            config["platforms"][self.key]["token_limit"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                "最大 Token 长度",
                "即每个请求中包含的 Token 的最大长度",
                init = init,
                value_changed = value_changed,
            )
        )