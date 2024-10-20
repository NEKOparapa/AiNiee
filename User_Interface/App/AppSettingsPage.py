
from PyQt5.Qt import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import SingleDirectionScrollArea

from AiNieeBase import AiNieeBase
from Widget.SwitchButtonCard import SwitchButtonCard

class AppSettingsPage(QWidget, AiNieeBase):

    DEFAULT = {
        "font_hinting": True,
    }

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 载入配置文件
        config = self.load_config()

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)

        # 设置滚动容器
        self.scroller = SingleDirectionScrollArea(self, orient = Qt.Vertical)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container.addWidget(self.scroller)

        # 设置容器
        self.vbox_parent = QWidget(self)
        self.vbox_parent.setStyleSheet("QWidget { background: transparent; }")
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下
        self.scroller.setWidget(self.vbox_parent)

        # 添加控件
        self.add_widget_01(self.vbox, config)

        # 填充
        self.vbox.addStretch(1)

    # 思维链模式
    def add_widget_01(self, parent, config):
        def init(widget):
            widget.set_checked(config.get("font_hinting"))
            
        def checked_changed(widget, checked: bool):
            config = self.load_config()
            config["font_hinting"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "应用内字体优化", 
                "启用此功能后，应用内字体会更加圆润，但是边缘会稍显模糊（切换将在应用重启后生效）",
                init = init,
                checked_changed = checked_changed,
            )
        )