import os
import sys
import json
import subprocess

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QFileDialog

from qfluentwidgets import PushButton
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import SwitchButton
from qfluentwidgets import SingleDirectionScrollArea

from Base.Base import Base
from Widget.EmptyCard import EmptyCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.LineEditCard import LineEditCard
from Widget.SwitchButtonCard import SwitchButtonCard

class AppSettingsPage(QWidget, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "proxy_url": "",
            "proxy_enable": False,
            "font_hinting": True,
            "scale_factor": "AUTO",
            "interface_language_setting": "简中",
            "auto_check_update": True,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

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
        self.add_widget_proxy(self.vbox, config)
        self.add_widget_font_hinting(self.vbox, config)
        self.add_widget_auto_check_update(self.vbox, config) # 使用子线程进行更新检查
        self.add_widget_debug_mode(self.vbox, config)
        self.add_widget_scale_factor(self.vbox, config)
        self.add_widget_interface_language_setting(self.vbox, config)

        # 填充
        self.vbox.addStretch(1)

    # 网络代理地址
    def add_widget_proxy(self, parent, config) -> None:

        def checked_changed(swicth_button, checked: bool) -> None:
            swicth_button.setChecked(checked)

            config = self.load_config()
            config["proxy_enable"] = checked
            self.save_config(config)

            # 获取并设置网络代理
            proxy_url = config["proxy_url"]
            if checked == False or proxy_url == "":
                os.environ.pop("http_proxy", None)
                os.environ.pop("https_proxy", None)
                info = self.tra("网络代理已关闭")
                self.info(info)
            else:
                os.environ["http_proxy"] = proxy_url
                os.environ["https_proxy"] = proxy_url
                info = self.tra("网络代理已启用，代理地址")
                self.info(f"{info}：{proxy_url}")

        def init(widget) -> None:
            widget.set_text(config.get("proxy_url"))
            widget.set_fixed_width(256)
            widget.set_placeholder_text(self.tra("请输入网络代理地址"))

            swicth_button = SwitchButton()
            swicth_button.setOnText(self.tra("启用"))
            swicth_button.setOffText(self.tra("禁用"))
            swicth_button.setChecked(config.get("proxy_enable", False))
            swicth_button.checkedChanged.connect(lambda checked: checked_changed(swicth_button, checked))
            widget.add_spacing(8)
            widget.add_widget(swicth_button)

            # 获取并设置网络代理
            checked = config["proxy_enable"]
            proxy_url = config["proxy_url"]
            if checked == False or proxy_url == "":
                os.environ.pop("http_proxy", None)
                os.environ.pop("https_proxy", None)
            else:
                os.environ["http_proxy"] = proxy_url
                os.environ["https_proxy"] = proxy_url
                info = self.tra("网络代理已启用，代理地址")
                self.info(f"{info}：{proxy_url}")

        def text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["proxy_url"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("网络代理地址"),
                self.tra("启用该功能后，将使用设置的代理地址向接口发送请求，例如 http://127.0.0.1:7890"),
                init = init,
                text_changed = text_changed,
            )
        )

    # 应用字体优化
    def add_widget_font_hinting(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_checked(config.get("font_hinting"))

        def checked_changed(widget, checked: bool) -> None:
            config = self.load_config()
            config["font_hinting"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("应用字体优化"),
                self.tra("启用此功能后，字体的边缘渲染将更加圆润（将在应用重启后生效）"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 调整模式
    def add_widget_debug_mode(self, parent, config) -> None:
        def init(widget) -> None:
            debug_path = os.path.join(".", "debug.txt")
            widget.set_checked(os.path.isfile(debug_path))

        def checked_changed(widget, checked: bool) -> None:
            debug_path = os.path.join(".", "debug.txt")
            if checked == True:
                open(debug_path, "w").close()
            else:
                os.remove(debug_path) if os.path.isfile(debug_path) else None

            # 重置调试模式检查状态
            self.reset_debug()

        parent.addWidget(
            SwitchButtonCard(
                self.tra("调试模式"),
                self.tra("启用此功能后，应用将显示额外的调试信息"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 全局缩放比例
    def add_widget_scale_factor(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_current_index(max(0, widget.find_text(config.get("scale_factor"))))

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["scale_factor"] = text
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("全局缩放比例"),
                self.tra("启用此功能后，应用界面将按照所选比例进行缩放（将在应用重启后生效）"),
                ["AUTO", "50%", "75%", "150%", "200%"],
                init = init,
                current_text_changed = current_text_changed,
            )
        )


    # 语言
    def add_widget_interface_language_setting(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_current_index(max(0, widget.find_text(config.get("interface_language_setting"))))

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["interface_language_setting"] = text
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("界面语言设置"),
                self.tra("应用界面将按照所选语言进行显示（将在应用重启后生效）"),
                ["简中", "繁中", "English", "日本語"],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 自动检查更新
    def add_widget_auto_check_update(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_checked(config.get("auto_check_update", True))

        def checked_changed(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_check_update"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动检查更新"),
                self.tra("启用此功能后，应用将在启动时自动检查是否有新版本"),
                init = init,
                checked_changed = checked_changed,
            )
        )


