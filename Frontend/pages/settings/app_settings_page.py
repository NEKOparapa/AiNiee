import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtCore import QSignalBlocker
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import ColorPickerButton
from qfluentwidgets import PushButton
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import SwitchButton
from qfluentwidgets import SingleDirectionScrollArea
from qfluentwidgets import setThemeColor

from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin
from Frontend.core.log import LogMixin
from Frontend.core.log_system import redact
from Frontend.components.toast import ToastMixin
from Frontend.components.cards.empty_card import EmptyCard
from Frontend.components.cards.combo_box_card import ComboBoxCard
from Frontend.components.cards.line_edit_card import LineEditCard
from Frontend.components.cards.switch_button_card import SwitchButtonCard
from Frontend.components.segmented_control import SegmentedControl
from Frontend.platform.file_dialogs import get_existing_directory, get_open_file_name
from Frontend.platform.process import launch_desktop
from Frontend.services.backend_client import BackendError

class AppSettingsPage(QWidget, ConfigMixin, LogMixin, ToastMixin, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = self.get_default_section("AppSettingsPage")

        # 载入并保存默认配置
        config = self.initialize_config()

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
        self.add_widget_theme(self.vbox, config, window)
        self.add_widget_accent_color(self.vbox, config)
        self.add_widget_backend_connection(self.vbox, config)
        self.add_widget_mcp(self.vbox, config)
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


    def add_widget_backend_connection(self, parent, config) -> None:
        def init_backend(widget):
            widget.set_text(self.config_backend().url)
            widget.set_fixed_width(280)
            widget.line_edit.setReadOnly(True)
        parent.addWidget(LineEditCard(
            self.tra("后端服务"),
            self.tra("当前连接地址；更换后端后需要重新启动桌面端。"),
            init=init_backend,
        ))

    def add_widget_mcp(self, parent, config) -> None:
        self._mcp_enabled = config.get("mcp_enable", True)

        def checked_changed(widget, checked: bool) -> None:
            try:
                saved = self.save_config({"mcp_enable": checked})
            except (BackendError, ValueError) as error:
                with QSignalBlocker(widget.switch_button):
                    widget.set_checked(self._mcp_enabled)
                self.error_toast(self.tra("MCP 设置保存失败"), redact(str(error)))
                return
            self._mcp_enabled = saved.get("mcp_enable", checked)
            with QSignalBlocker(widget.switch_button):
                widget.set_checked(self._mcp_enabled)

        self.mcp_switch_card = SwitchButtonCard(
            self.tra("MCP 服务"),
            self.tra("允许 MCP 客户端提交、查询和取消翻译任务。立即生效，关闭后已提交的任务继续执行。"),
            init=lambda widget: widget.set_checked(self._mcp_enabled),
            checked_changed=checked_changed,
        )
        self.mcp_switch_card.description_label.setWordWrap(True)
        self.mcp_switch_card.container.setStretch(0, 1)
        self.mcp_switch_card.container.setStretch(1, 0)
        parent.addWidget(self.mcp_switch_card)

        def copy_address() -> None:
            QApplication.clipboard().setText(self.mcp_address_card.get_text())
            self.success_toast("", self.tra("MCP 地址已复制"))

        def init_address(widget) -> None:
            address = self.config_backend().mcp_url
            widget.set_text(address)
            widget.set_fixed_width(280)
            widget.line_edit.setReadOnly(True)
            widget.line_edit.setClearButtonEnabled(False)
            widget.line_edit.setCursorPosition(0)
            widget.line_edit.setToolTip(address)
            self.mcp_copy_button = PushButton(self.tra("复制地址"), self)
            self.mcp_copy_button.setIcon(FluentIcon.COPY)
            self.mcp_copy_button.clicked.connect(copy_address)
            widget.add_spacing(8)
            widget.add_widget(self.mcp_copy_button)

        self.mcp_address_card = LineEditCard(
            self.tra("MCP 连接地址"),
            self.tra("客户端请选择 Streamable HTTP，地址随当前后端自动生成。"),
            init=init_address,
        )
        self.mcp_address_card.description_label.setWordWrap(True)
        self.mcp_address_card.hbox.setStretch(0, 1)
        self.mcp_address_card.hbox.setStretch(1, 0)
        parent.addWidget(self.mcp_address_card)

    # 主题（跟随系统 / 浅色 / 深色，连体分段控件）
    def add_widget_theme(self, parent, config, window) -> None:
        theme_items = [
            ("auto", self.tra("跟随系统")),
            ("light", self.tra("浅色")),
            ("dark", self.tra("深色")),
        ]

        def init(widget) -> None:
            current = config.get("theme", "auto")
            if current not in ("auto", "light", "dark"):
                current = "auto"

            segmented = SegmentedControl(widget)
            for mode, text in theme_items:
                segmented.add_item(mode, text)
            segmented.set_current_key(current)
            if hasattr(window, "apply_theme_mode"):
                segmented.currentChanged.connect(window.apply_theme_mode)
            widget.add_widget(segmented)

        parent.addWidget(
            EmptyCard(
                self.tra("主题"),
                self.tra("选择浅色、深色，或跟随系统外观自动切换"),
                init=init,
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

    # 应用配置切换
    def add_widget_app_profile(self, parent, config, window) -> None:

        # 重启应用
        def restart_app() -> None:
            launch_desktop()
            sys.exit(0)

        # 导入配置文件
        def import_profile_file(path) -> None:
            # 确认框
            message_box = MessageBox(self.tra("警告"), self.tra("是否确认导入选中的配置文件,导入后应用将自动重启"), window)
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))
            if not message_box.exec():
                return
            try:
                self.import_config(path)
            except Exception as error:
                self.error_toast(self.tra("导入失败"), str(error))
                return
            self.success_toast("", self.tra("配置文件导入成功,应用即将自动重启!"))

            # 重启应用
            QTimer.singleShot(1000, restart_app)

        # 导出配置文件
        def export_profile_file(path) -> None:
            try:
                result = self.export_config(path)
            except Exception as error:
                self.error_toast(self.tra("导出失败"), str(error))
                return
            info_cont = self.tra("配置已导出为") + f" {result['path']}"
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
