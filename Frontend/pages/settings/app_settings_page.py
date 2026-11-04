"""Application preferences arranged in the same groups as task settings."""

import os
import sys

from PyQt5.QtCore import QSignalBlocker, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QWidget
from qfluentwidgets import (
    ColorPickerButton, ComboBox, FluentIcon, LineEdit, MessageBox, PushButton,
    SwitchButton, qconfig, setThemeColor,
)

from Frontend.components.segmented_control import SegmentedControl
from Frontend.core.log import LogMixin
from Frontend.core.log_system import redact
from Frontend.pages.settings.grouped_settings_page import GroupedSettingsPage
from Frontend.platform.file_dialogs import get_existing_directory, get_open_file_name
from Frontend.platform.process import launch_desktop


class AppSettingsPage(GroupedSettingsPage, LogMixin):
    DEFAULT_ACCENT = "#808b9d"

    def __init__(self, text, window):
        self._app_window = window
        self._importing = False
        self._selected_theme = "auto"
        self.default = self.get_default_section("AppSettingsPage")
        super().__init__(text, window)

    def _build_fields(self):
        self.layout().setContentsMargins(28, 24, 24, 20)
        self.editor_layout.setSpacing(14)
        appearance = self._add_section("外观与语言", FluentIcon.PALETTE)
        self.language_combo = ComboBox(self.editor)
        self.language_combo.addItems(self.INTERFACE_LANGUAGES)
        appearance.add_field("界面语言设置", self.language_combo,
                             "应用界面将按照所选语言进行显示(将在应用重启后生效)")
        self.theme_control = SegmentedControl(self.editor)
        for mode, label in (("auto", "跟随系统"), ("light", "浅色"), ("dark", "深色")):
            self.theme_control.add_item(mode, self.tra(label))
        appearance.add_field("主题", self.theme_control, "选择浅色、深色，或跟随系统外观自动切换")
        self.theme_control.setFixedWidth(360)
        self.accent_picker = ColorPickerButton(QColor(self.DEFAULT_ACCENT), self.tra("主题色"), self.editor, enableAlpha=False)
        self.accent_reset_button = PushButton(self.tra("恢复默认"), self.editor)
        appearance.add_field("主题色", self._actions(self.accent_picker, self.accent_reset_button),
                             "设置应用强调色，立即生效；部分自定义组件需重新打开后应用")

        connection = self._add_section("网络与服务", FluentIcon.GLOBE)
        self.proxy_switch = SwitchButton(self.editor)
        connection.add_field("网络代理", self.proxy_switch,
                             "启用该功能后,将使用设置的代理地址向接口发送请求,例如 http://127.0.0.1:7890")
        self.proxy_edit = LineEdit(self.editor)
        self.proxy_edit.setPlaceholderText(self.tra("请输入网络代理地址"))
        connection.add_field("网络代理地址", self.proxy_edit)
        self.proxy_edit.setFixedWidth(360)
        self.backend_address = self._address_edit()
        connection.add_field("后端服务", self.backend_address, "当前连接地址；更换后端后需要重新启动桌面端。")
        self.backend_address.setFixedWidth(360)
        self.mcp_switch = SwitchButton(self.editor)
        connection.add_field("MCP 服务", self.mcp_switch,
                             "允许 MCP 客户端提交、查询和取消翻译任务。立即生效，关闭后已提交的任务继续执行。")
        self.mcp_address = self._address_edit()
        self.mcp_copy_button = PushButton(FluentIcon.COPY, self.tra("复制地址"), self.editor)
        address_actions = self._actions(self.mcp_address, self.mcp_copy_button)
        connection.add_field("MCP 连接地址", address_actions,
                             "客户端请选择 Streamable HTTP，地址随当前后端自动生成。")
        address_actions.setFixedWidth(360)

        profiles = self._add_section("配置管理", FluentIcon.DOCUMENT, expanded=False)
        self.import_button = PushButton(FluentIcon.DOWNLOAD, self.tra("导入"), self.editor)
        self.export_button = PushButton(FluentIcon.SHARE, self.tra("导出"), self.editor)
        profiles.add_field("应用配置切换", self._actions(self.import_button, self.export_button),
                           "可以将当前应用的所有设置导出为配置文件,以方便根据不同项目切换配置(导入配置后应用将自动重启)")

        updates = self._add_section("应用更新", FluentIcon.UPDATE, expanded=False)
        self.auto_update_switch = SwitchButton(self.editor)
        updates.add_field("自动检查更新", self.auto_update_switch,
                          "启用此功能后,应用将在启动时自动检查是否有新版本")
        self.check_update_button = PushButton(FluentIcon.UPDATE, self.tra("检查更新"), self.editor)
        updates.add_field("检查更新", self.check_update_button, "点击按钮手动检查是否有新版本可用")

        self.proxy_edit.textChanged.connect(self._schedule_save)
        self.proxy_edit.editingFinished.connect(self._save_settings)
        self.proxy_switch.checkedChanged.connect(self._save_immediately)
        self.language_combo.currentIndexChanged.connect(self._save_immediately)
        self.auto_update_switch.checkedChanged.connect(self._save_immediately)
        self.mcp_switch.checkedChanged.connect(self._on_mcp_changed)
        self.theme_control.currentChanged.connect(self._on_theme_changed)
        self.accent_picker.colorChanged.connect(self._on_accent_changed)
        self.accent_reset_button.clicked.connect(lambda: self._on_accent_changed(QColor(self.DEFAULT_ACCENT)))
        self.mcp_copy_button.clicked.connect(self._copy_mcp_address)
        self.import_button.clicked.connect(self._choose_import)
        self.export_button.clicked.connect(self._choose_export)
        self.check_update_button.clicked.connect(self._check_updates)

    def _actions(self, *widgets):
        actions = QWidget(self.editor)
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for widget in widgets:
            layout.addWidget(widget)
        return actions

    def _address_edit(self):
        edit = LineEdit(self.editor)
        edit.setReadOnly(True)
        edit.setClearButtonEnabled(False)
        return edit

    def _read_settings(self, config):
        return {**self.default, "theme": "auto", "accent_color": self.DEFAULT_ACCENT, **config}

    def _load_fields(self, values):
        self.proxy_edit.setText(values.get("proxy_url", ""))
        self.proxy_switch.setChecked(values.get("proxy_enable", False))
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findText(values.get("interface_language_setting", "简中"))))
        self.auto_update_switch.setChecked(values.get("auto_check_update", True))
        self.mcp_switch.setChecked(values.get("mcp_enable", True))
        mode = values.get("theme", "auto")
        self._selected_theme = mode if mode in ("auto", "light", "dark") else "auto"
        self.theme_control.set_current_key(self._selected_theme)
        color = QColor(values.get("accent_color", self.DEFAULT_ACCENT))
        self.accent_picker.setColor(color if color.isValid() else QColor(self.DEFAULT_ACCENT))
        for edit, address in ((self.backend_address, self.config_backend().url),
                              (self.mcp_address, self.config_backend().mcp_url)):
            edit.setText(address)
            edit.setCursorPosition(0)
            edit.setToolTip(address)

    def _form_values(self):
        return {
            "proxy_url": self.proxy_edit.text().strip(),
            "proxy_enable": self.proxy_switch.isChecked(),
            "interface_language_setting": self.language_combo.currentText(),
            "auto_check_update": self.auto_update_switch.isChecked(),
            "mcp_enable": self.mcp_switch.isChecked(),
            "theme": self._selected_theme,
            "accent_color": self.accent_picker.color.name(),
        }

    def _build_update(self, current, values):
        return {key: value for key, value in values.items()
                if self._baseline is None or value != self._baseline.get(key)}

    def _apply_config(self, config):
        super()._apply_config(config)
        self._apply_runtime(config)

    def _save_settings(self, *, report_validation=True):
        if self._importing:
            return True
        changed = not self._loading and self._is_dirty()
        saved = super()._save_settings(report_validation=report_validation)
        if changed and saved:
            self._apply_runtime(self._config_snapshot)
        return saved

    def _apply_runtime(self, config):
        # Only apply live effects after the backend has accepted the settings.
        proxy = config.get("proxy_url", "") if config.get("proxy_enable", False) else ""
        for key in ("http_proxy", "https_proxy"):
            if proxy:
                os.environ[key] = proxy
            else:
                os.environ.pop(key, None)
        self._app_window.apply_theme_mode(config.get("theme", "auto"), persist=False)
        color = QColor(config.get("accent_color", self.DEFAULT_ACCENT))
        if color.isValid() and color != qconfig.get(qconfig.themeColor):
            setThemeColor(color)

    def _save_immediately(self, *_):
        if not self._loading:
            self._save_settings()

    def _on_mcp_changed(self, _checked):
        if self._loading:
            return
        if not self._save_settings():
            with QSignalBlocker(self.mcp_switch):
                self.mcp_switch.setChecked(self._baseline["mcp_enable"])

    def _on_theme_changed(self, mode):
        self._selected_theme = mode
        self._save_immediately()

    def _on_accent_changed(self, color):
        self.accent_picker.setColor(color)
        self._save_immediately()

    def _copy_mcp_address(self):
        QApplication.clipboard().setText(self.mcp_address.text())
        self.success_toast("", self.tra("MCP 地址已复制"))

    def _check_updates(self):
        if not self.prepare_to_leave():
            return
        self.check_update_button.setText(self.tra("正在检查更新..."))
        self.check_update_button.setEnabled(False)
        try:
            self._app_window.show_update_dialog()
        finally:
            QTimer.singleShot(1000, self._reset_update_button)

    def _reset_update_button(self):
        self.check_update_button.setText(self.tra("检查更新"))
        self.check_update_button.setEnabled(True)

    def _choose_import(self):
        path, _ = get_open_file_name(self, self.tra("选择文件"), "", self.tra("JSON 配置文件 (*.json)"))
        if path:
            self._import_profile(path)

    def _import_profile(self, path):
        dialog = MessageBox(self.tra("警告"), self.tra("是否确认导入选中的配置文件,导入后应用将自动重启"), self._app_window)
        dialog.yesButton.setText(self.tra("确认"))
        dialog.cancelButton.setText(self.tra("取消"))
        accepted = dialog.exec()
        dialog.deleteLater()
        if not accepted or not self.prepare_to_leave():
            return
        try:
            self.import_config(path)
        except Exception as error:
            self.error_toast(self.tra("导入失败"), redact(str(error)))
            return
        self._importing = True
        self._save_timer.stop()
        self.editor.setEnabled(False)
        self.success_toast("", self.tra("配置文件导入成功,应用即将自动重启!"))
        QTimer.singleShot(1000, self._restart_app)

    def _restart_app(self):
        launch_desktop()
        sys.exit(0)

    def _choose_export(self):
        path = get_existing_directory(self, self.tra("选择文件夹"), "")
        if path:
            self._export_profile(path)

    def _export_profile(self, path):
        if not self.prepare_to_leave():
            return
        try:
            result = self.export_config(path)
        except Exception as error:
            self.error_toast(self.tra("导出失败"), redact(str(error)))
            return
        self.success_toast("", self.tra("配置已导出为") + f" {result['path']}")
