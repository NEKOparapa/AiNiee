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
        self.add_widget_debug_mode(self.vbox, config)
        self.add_widget_scale_factor(self.vbox, config)
        self.add_widget_interface_language_setting(self.vbox, config)
        self.add_widget_app_profile(self.vbox, config, window)

        # 填充
        self.vbox.addStretch(1)

    # 网络代理地址
    def add_widget_proxy(self, parent, config) -> None:

        def checked_changed(swicth_button, checked: bool) -> None:
            swicth_button.setChecked(checked)

            config = self.load_config()
            config["proxy_enable"] = checked
            self.save_config(config)

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



    # 应用配置切换
    def add_widget_app_profile(self, parent, config, window) -> None:

        # 重启应用
        def restart_app() -> None:
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)

        # 导入配置文件
        def import_profile_file(path) -> None:
            profile = {}

            if os.path.exists(path):
                with open(path, "r", encoding = "utf-8") as reader:
                    profile = json.load(reader)
            else:
                self.error_toast("", self.tra("配置文件不存在！"))
                return

            if len(profile) == 0 or "target_platform" not in profile:
                self.error_toast("", self.tra("配置文件内容未通过校验！"))
                return

            # 确认框
            message_box = MessageBox("Warning", self.tra("是否确认导入选中的配置文件，导入后应用将自动重启"), window)
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))
            if message_box.exec():
                self.success_toast("", self.tra("配置文件导入成功，应用即将自动重启！"))
            else:
                return

            # 保存配置文件
            config = self.load_config()
            for k, v in profile.items():
                if k != "platforms":
                    config[k] = v
            self.save_config(config)

            # 重启应用
            QTimer.singleShot(1000, restart_app)

        # 导出配置文件
        def export_profile_file(path) -> None:
            config = self.load_config()
            del config["platforms"]

            with open(f"{path}/ainiee_profile.json", "w", encoding = "utf-8") as writer:
                writer.write(json.dumps(config, indent = 4, ensure_ascii = False))

            info_cont = self.tra("配置已导出为") + " \"ainiee_profile.json\" ..."
            self.success_toast("", info_cont)

        # 导入按钮点击事件
        def on_improt_button_clicked() -> None:
            path, _ = QFileDialog.getOpenFileName(None, self.tra("选择文件"), "", "json files (*.json)")

            if path == None or path == "":
                return

            import_profile_file(path)
        # 导出按钮点击事件
        def on_exprot_button_clicked() -> None:
            path = QFileDialog.getExistingDirectory(None, self.tra("选择文件夹"), "")

            if path == None or path == "":
                return

            export_profile_file(path)

        def init(widget) -> None:
            improt_button = PushButton(self.tra("导入"), self)
            improt_button.setIcon(FluentIcon.DOWNLOAD)
            improt_button.setContentsMargins(4, 0, 4, 0)
            improt_button.clicked.connect(on_improt_button_clicked)

            export_button = PushButton(self.tra("导出"), self)
            export_button.setIcon(FluentIcon.SHARE)
            export_button.setContentsMargins(4, 0, 4, 0)
            export_button.clicked.connect(on_exprot_button_clicked)

            widget.add_widget(improt_button)
            widget.add_spacing(16)
            widget.add_widget(export_button)

        parent.addWidget(
            EmptyCard(
                self.tra("应用配置切换"),
                self.tra("可以将当前应用的除接口信息以外的所有设置导出为配置文件，以方便根据不同项目切换配置（导入配置后应用将自动重启）"),
                init = init,
            )
        )