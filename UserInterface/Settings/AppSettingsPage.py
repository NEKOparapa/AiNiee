import os
import sys
import json
import subprocess

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import ColorPickerButton
from qfluentwidgets import PushButton
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import SwitchButton
from qfluentwidgets import SingleDirectionScrollArea
from qfluentwidgets import setThemeColor

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from UserInterface.Widget.Toast import ToastMixin
from UserInterface.Widget.EmptyCard import EmptyCard
from UserInterface.Widget.ComboBoxCard import ComboBoxCard
from UserInterface.Widget.LineEditCard import LineEditCard
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard
from UserInterface.Widget.LineEditCard import LineEditCard
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard 
from UserInterface.Native.FileDialogProvider import get_existing_directory, get_open_file_name

class AppSettingsPage(QWidget, ConfigMixin, LogMixin, ToastMixin, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "proxy_url": "",
            "proxy_enable": False,
            "scale_factor": "AUTO",
            "interface_language_setting": "简中",
            "auto_check_update": True,
            "label_input_exclude_rule": "",
            "http_server_enable": False,
            "http_listen_address": "127.0.0.1:3388",
            "http_callback_url": "",
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
        self.vbox.setContentsMargins(24, 24, 24, 24)  # 左、上、右、下
        self.scroller.setWidget(self.vbox_parent)

        # 添加控件
        self.add_widget_app_profile(self.vbox, config, window)
        self.add_widget_proxy(self.vbox, config)
        self.add_widget_interface_language_setting(self.vbox, config)
        self.add_widget_auto_check_update(self.vbox, config)
        self.add_widget_check_update(self.vbox, config, window)
        self.add_widget_scale_factor(self.vbox, config)
        self.add_widget_accent_color(self.vbox, config)
        self.add_widget_exclude_rule(self.vbox, config)
        self.add_widget_http_service(self.vbox, config)
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
                info = self.tra("网络代理已启用,代理地址")
                self.info(f"{info}:{proxy_url}")

        def init(widget) -> None:
            widget.set_text(config.get("proxy_url"))
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
                info = self.tra("网络代理已启用,代理地址")
                self.info(f"{info}:{proxy_url}")

        def text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["proxy_url"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("网络代理地址"),
                self.tra("启用该功能后,将使用设置的代理地址向接口发送请求,例如 http://127.0.0.1:7890"),
                init=init,
                text_changed=text_changed,
            )
        )


    # 3. 新增生成 UI 的方法
    def add_widget_http_service(self, parent, config) -> None:
        """HTTP 服务设置"""
        
        # --- 开关 ---
        def init_enable(widget) -> None:
            widget.set_checked(config.get("http_server_enable", False))

        def checked_changed_enable(widget, checked: bool) -> None:
            config = self.load_config()
            config["http_server_enable"] = checked
            self.save_config(config)
            if checked:
                self.info_toast(self.tra("提示"), self.tra("请重启应用以启动 HTTP 服务"))
            else:
                self.info_toast(self.tra("提示"), self.tra("请重启应用以关闭 HTTP 服务"))

        parent.addWidget(
            SwitchButtonCard(
                self.tra("启用 HTTP 监听服务"),
                self.tra("开启后可以通过 HTTP 请求控制翻译 (需重启生效)"),
                init=init_enable,
                checked_changed=checked_changed_enable,
            )
        )

        # --- 监听地址 (合并) ---
        def init_address(widget) -> None:
            widget.set_text(config.get("http_listen_address", "127.0.0.1:3388"))
            widget.set_placeholder_text("127.0.0.1:3388")

        def text_changed_address(widget, text: str) -> None:
            config = self.load_config()
            config["http_listen_address"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("监听地址与端口"),
                self.tra("格式为 IP:端口，例如 127.0.0.1:3388 (仅本机) 或 0.0.0.0:3388 (局域网)"),
                init=init_address,
                text_changed=text_changed_address,
            )
        )

        # --- 回调 URL ---
        def init_callback(widget) -> None:
            widget.set_text(config.get("http_callback_url", ""))
            widget.set_placeholder_text("http://localhost:3000/webhook")

        def text_changed_callback(widget, text: str) -> None:
            config = self.load_config()
            config["http_callback_url"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("完成回调 URL"),
                self.tra("翻译完成后，向该地址发送 POST 请求。留空则不启用。"),
                init=init_callback,
                text_changed=text_changed_callback,
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
                self.tra("启用此功能后,应用界面将按照所选比例进行缩放(将在应用重启后生效)"),
                ["AUTO", "50%", "75%", "125%", "150%", "200%"],
                init=init,
                current_text_changed=current_text_changed,
            )
        )

    # 主题色
    def add_widget_accent_color(self, parent, config) -> None:
        DEFAULT_ACCENT = "#808b9d"

        def on_color_changed(color: QColor) -> None:
            hex_value = color.name()
            cfg = self.load_config()
            cfg["accent_color"] = hex_value
            self.save_config(cfg)
            setThemeColor(color)

        def init(widget) -> None:
            initial = QColor(config.get("accent_color", DEFAULT_ACCENT))
            picker = ColorPickerButton(initial, self.tra("主题色"), self, enableAlpha=False)
            picker.colorChanged.connect(on_color_changed)

            def reset_to_default():
                default = QColor(DEFAULT_ACCENT)
                picker.setColor(default)
                on_color_changed(default)

            reset_button = PushButton(self.tra("恢复默认"), self)
            reset_button.clicked.connect(reset_to_default)

            widget.add_widget(picker)
            widget.add_spacing(8)
            widget.add_widget(reset_button)

        parent.addWidget(
            EmptyCard(
                self.tra("主题色"),
                self.tra("设置应用强调色，立即生效；部分自定义组件需重新打开后应用"),
                init=init,
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
                self.tra("应用界面将按照所选语言进行显示(将在应用重启后生效)"),
                ["简中", "繁中", "English", "日本語"],
                init=init,
                current_text_changed=current_text_changed,
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
                self.tra("启用此功能后,应用将在启动时自动检查是否有新版本"),
                init=init,
                checked_changed=checked_changed,
            )
        )

    # 手动检查更新
    def add_widget_check_update(self, parent, config, window) -> None:
        """手动检查更新按钮"""

        def on_check_button_clicked(check_button) -> None:
            """检查更新按钮点击事件"""
            # 更新按钮文本,提示正在检查
            original_text = check_button.text()
            check_button.setText(self.tra("正在检查更新..."))
            check_button.setEnabled(False)

            # 显示更新对话框
            window.show_update_dialog()

            # 恢复按钮文本和状态
            QTimer.singleShot(1000, lambda: (
                check_button.setText(original_text),
                check_button.setEnabled(True)
            ))

        def init(widget) -> None:
            check_button = PushButton(self.tra("检查更新"), self)
            check_button.setIcon(FluentIcon.UPDATE)
            check_button.setContentsMargins(4, 0, 4, 0)
            check_button.clicked.connect(lambda: on_check_button_clicked(check_button))

            widget.add_widget(check_button)

        parent.addWidget(
            EmptyCard(
                self.tra("检查更新"),
                self.tra("点击按钮手动检查是否有新版本可用"),
                init=init,
            )
        )

    def add_widget_exclude_rule(self, parent, config) -> None:
        """文件/目录排除规则"""
        def init(widget) -> None:
            widget.set_text(config.get("label_input_exclude_rule"))
            widget.set_placeholder_text(self.tra("*.log,aaa/*"))

        def text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["label_input_exclude_rule"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("文件/目录排除规则"),
                self.tra("*.log 表示排除所有结尾为 .log 的文件,aaa/* 表示排除输入文件夹下整个 aaa 目录,多个规则用英文逗号分隔"),
                init=init,
                text_changed=text_changed,
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
                with open(path, "r", encoding="utf-8") as reader:
                    profile = json.load(reader)
            else:
                self.error_toast("", self.tra("配置文件不存在!"))
                return

            # 确认框
            message_box = MessageBox(self.tra("警告"), self.tra("是否确认导入选中的配置文件,导入后应用将自动重启"), window)
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))
            if message_box.exec():
                self.success_toast("", self.tra("配置文件导入成功,应用即将自动重启!"))
            else:
                return

            # 保存配置文件
            config = self.load_config()
            for k, v in profile.items():
                config[k] = v
            self.save_config(config)

            # 重启应用
            QTimer.singleShot(1000, restart_app)

        # 导出配置文件
        def export_profile_file(path) -> None:
            config = self.load_config()

            with open(f"{path}/ainiee_profile.json", "w", encoding="utf-8") as writer:
                writer.write(json.dumps(config, indent=4, ensure_ascii=False))

            info_cont = self.tra("配置已导出为") + " \"ainiee_profile.json\" ..."
            self.success_toast("", info_cont)

        # 导入按钮点击事件
        def on_improt_button_clicked() -> None:
            path, _ = get_open_file_name(None, self.tra("选择文件"), "", self.tra("JSON 配置文件 (*.json)"))

            if path == None or path == "":
                return

            import_profile_file(path)

        # 导出按钮点击事件
        def on_exprot_button_clicked() -> None:
            path = get_existing_directory(None, self.tra("选择文件夹"), "")

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
                self.tra("可以将当前应用的所有设置导出为配置文件,以方便根据不同项目切换配置(导入配置后应用将自动重启)"),
                init=init,
            )
        )
