import os
import threading

import darkdetect
import requests
from PyQt5.QtCore import QThread, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QIcon
from PyQt5.QtWidgets import QAction, QApplication, QMenuBar
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    MessageBox,
    NavigationAvatarWidget,
    NavigationItemPosition,
    NavigationPushButton,
    SystemThemeListener,
    Theme,
    setTheme,
    setThemeColor,
)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import resource_path
from ModuleFolders.Infrastructure.Platform.PlatformPaths import is_macos
from ModuleFolders.Log.Log import LogMixin
from UserInterface.BaseNavigationItem import BaseNavigationItem
from UserInterface.EditView.EditViewPage import EditViewPage
from UserInterface.Native.MacOSUI import about_message, app_menu_title, command_shortcut
from UserInterface.Platform.PlatformPage import PlatformPage
from UserInterface.PromptSettings.PolishingSettings.PolishingSystemPromptPage import PolishingSystemPromptPage
from UserInterface.Settings.AppSettingsPage import AppSettingsPage
from UserInterface.Settings.OutputSettingsPage import OutputSettingsPage
from UserInterface.Settings.TaskSettingsPage import TaskSettingsPage
from UserInterface.Table.ExclusionListPage import ExclusionListPage
from UserInterface.Table.PromptDictionaryPage import PromptDictionaryPage
from UserInterface.Table.TextReplaceAPage import TextReplaceAPage
from UserInterface.Table.TextReplaceBPage import TextReplaceBPage
from UserInterface.PromptSettings.TranslationSettings.CharacterizationPromptPage import CharacterizationPromptPage
from UserInterface.PromptSettings.TranslationSettings.SystemPromptPage import SystemPromptPage
from UserInterface.PromptSettings.TranslationSettings.TranslationExamplePromptPage import TranslationExamplePromptPage
from UserInterface.PromptSettings.TranslationSettings.TranslationSettingsPage import TranslationSettingsPage
from UserInterface.PromptSettings.TranslationSettings.WorldBuildingPromptPage import WorldBuildingPromptPage
from UserInterface.PromptSettings.TranslationSettings.WritingStylePromptPage import WritingStylePromptPage
from UserInterface.VersionManager.VersionManager import VersionManager
from UserInterface.Widget.Toast import ToastMixin


# 自动检查更新线程
class UpdateCheckerThread(QThread):
    update_available_signal = pyqtSignal(bool, str, bool)

    def __init__(self, version_manager):
        super().__init__()
        self.version_manager = version_manager

    def run(self):
        # 在子线程中运行更新检查逻辑
        self.version_manager.check_error = None
        has_update, latest_version = self.version_manager.check_for_updates()
        check_failed = hasattr(self.version_manager, "check_error") and self.version_manager.check_error is not None
        self.update_available_signal.emit(has_update, latest_version, check_failed)


# 主窗口
class AppFluentWindow(FluentWindow, ConfigMixin, LogMixin, ToastMixin, Base):
    APP_WIDTH = 1600
    APP_HEIGHT = 900
    THEME_COLOR = "#808b9d"

    def __init__(self, version: str, cache_manager, file_reader) -> None:
        super().__init__()

        # 启动后台线程发送日活统计，不阻塞 UI
        def report_activity():
            try:
                requests.get("https://ai-niee-vercel.vercel.app/api/track", timeout=5)
            except Exception as error:
                # 统计失败不影响程序运行
                self.debug(f"Activity report failed: {error}")

        # 设置 daemon=True，确保主程序退出时线程也会自动关闭
        threading.Thread(target=report_activity, daemon=True).start()

        # 默认配置
        self.default = {
            "theme": "auto",
            "accent_color": self.THEME_COLOR,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 更换界面显示的语言
        ConfigMixin.multilingual_interface_dict = self.load_translations(ConfigMixin.translation_json_file)
        ConfigMixin.current_interface_language = config.get("interface_language_setting", "简中")
        self.info(f"Current Interface Language: {ConfigMixin.current_interface_language}")

        # 设置主题颜色与主题
        self._theme_mode = config.get("theme", "auto")
        setThemeColor(config.get("accent_color", self.THEME_COLOR))
        setTheme(self._theme_for_mode(self._theme_mode))

        self.systemThemeListener = SystemThemeListener(self)
        self.systemThemeListener.systemThemeChanged.connect(self._on_system_theme_changed)
        self.systemThemeListener.start()

        # 设置窗口属性
        desktop = QApplication.desktop().availableGeometry()
        initial_width = int(desktop.width() * 0.8)
        initial_height = int(desktop.height() * 0.8)
        self.resize(initial_width, initial_height)
        self.setWindowTitle(version)
        self.setWindowIcon(QIcon(str(resource_path("Logo", "Avatar.png"))))
        self.titleBar.iconLabel.hide()

        # 初始化版本管理器，并在应用加载完成后异步检查更新
        self.version_manager = VersionManager(self, version)
        QTimer.singleShot(3000, self.check_for_updates)

        # 设置启动位置
        desktop = QApplication.desktop().availableGeometry()
        self.move(desktop.width() // 2 - self.width() // 2, desktop.height() // 2 - self.height() // 2)

        # 设置侧边栏属性
        self.navigationInterface.setExpandWidth(226)
        self.navigationInterface.expand(useAni=False)
        self.navigationInterface.setUpdateIndicatorPosOnCollapseFinished(True)
        self.navigationInterface.panel.setReturnButtonVisible(False)

        # 添加页面
        self.add_pages(cache_manager, file_reader)
        self.install_macos_menu()

    # 窗口关闭函数
    def closeEvent(self, event) -> None:
        info_cont = self.tra("确定是否退出程序") + " ... ？"
        message_box = MessageBox("Warning", info_cont, self)
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))

        if message_box.exec():
            self.emit(Base.EVENT.APP_SHUT_DOWN, {})
            self.info(self.tra("主窗口已关闭，稍后应用将自动退出") + " ... ")
            if hasattr(self, "systemThemeListener"):
                self.systemThemeListener.terminate()
                self.systemThemeListener.deleteLater()
            event.accept()
        else:
            event.ignore()

    def _on_system_theme_changed(self) -> None:
        if self._theme_mode == "auto":
            setTheme(self._theme_for_mode("auto"))

    # 切换主题
    _THEME_CYCLE = {"auto": "light", "light": "dark", "dark": "auto"}

    def toggle_theme(self) -> None:
        next_mode = self._THEME_CYCLE.get(self._theme_mode, "auto")
        self._theme_mode = next_mode

        setTheme(self._theme_for_mode(next_mode))
        self._update_theme_button(next_mode)
        self.save_config({"theme": next_mode})
        self.info_toast(self.tra("主题切换"), self._toast_for_mode(next_mode))

    @staticmethod
    def _theme_for_mode(mode: str) -> Theme:
        if mode == "auto":
            return Theme.DARK if darkdetect.theme() == "Dark" else Theme.LIGHT
        return Theme.DARK if mode == "dark" else Theme.LIGHT

    @staticmethod
    def _icon_for_mode(mode: str):
        return {
            "light": FluentIcon.BRIGHTNESS,
            "auto": FluentIcon.CONSTRACT,
            "dark": FluentIcon.QUIET_HOURS,
        }.get(mode, FluentIcon.CONSTRACT)

    def _toast_for_mode(self, mode: str) -> str:
        return {
            "light": self.tra("已切换至浅色主题"),
            "dark": self.tra("已切换至深色主题"),
            "auto": self.tra("已切换至跟随系统"),
        }.get(mode, "")

    def _update_theme_button(self, mode: str) -> None:
        if hasattr(self, "theme_nav_button"):
            self.theme_nav_button.setIcon(self._icon_for_mode(mode))

    # 打开项目主页
    def open_project_page(self) -> None:
        QDesktopServices.openUrl(QUrl("https://github.com/NEKOparapa/AiNiee"))

    def install_macos_menu(self) -> None:
        if not is_macos():
            return

        # FluentWindow 不是 QMainWindow，macOS 原生菜单栏用独立 QMenuBar 挂到系统菜单。
        menu_bar = QMenuBar(None)
        menu_bar.setNativeMenuBar(True)
        self.macos_menu_bar = menu_bar

        app_menu = menu_bar.addMenu(app_menu_title())
        about_action = QAction(self.tra("关于 AiNiee"), self)
        about_action.setMenuRole(QAction.AboutRole)
        about_action.triggered.connect(
            lambda: MessageBox(
                self.tra("关于 AiNiee"),
                about_message(self.windowTitle(), self.tra),
                self,
            ).exec()
        )

        preferences_action = QAction(self.tra("偏好设置..."), self)
        preferences_action.setMenuRole(QAction.PreferencesRole)
        preferences_action.setShortcut(command_shortcut(","))
        preferences_action.triggered.connect(lambda: self.switchTo(self.app_settings_page))

        quit_action = QAction(self.tra("退出 AiNiee"), self)
        quit_action.setMenuRole(QAction.QuitRole)
        quit_action.setShortcut(command_shortcut("Q"))
        quit_action.triggered.connect(self.close)

        app_menu.addAction(about_action)
        app_menu.addSeparator()
        app_menu.addAction(preferences_action)
        app_menu.addSeparator()
        app_menu.addAction(quit_action)

    # 显示更新对话框
    def show_update_dialog(self) -> None:
        self.version_manager.show_update_dialog()

    # 检查更新
    def check_for_updates(self) -> None:
        config = self.load_config()
        if config.get("auto_check_update", True):
            self.update_checker_thread = UpdateCheckerThread(self.version_manager)
            self.update_checker_thread.update_available_signal.connect(self._on_update_check_completed)
            self.update_checker_thread.start()

    # 更新检查完成的回调
    def _on_update_check_completed(self, has_update: bool, latest_version: str, check_failed: bool) -> None:
        if check_failed:
            self.warning_toast(self.tra("更新检查失败"), self.tra("请检查报错信息"))
        elif has_update:
            self.success_toast(
                self.tra("发现新版本"),
                self.tra("当前版本: {0}, 最新版本: {1}, 点击更新按钮进行更新").format(
                    self.version_manager.current_version,
                    latest_version,
                ),
            )
        else:
            self.info_toast(self.tra("更新检查"), self.tra("当前已是最新版本"))

    # 开始添加页面
    def add_pages(self, cache_manager, file_reader) -> None:
        # ===== 快速开始 =====
        self.navigationInterface.addItemHeader(self.tra("快速开始"), NavigationItemPosition.SCROLL)
        self.add_project_pages(cache_manager, file_reader)

        # ===== 任务配置 =====
        self.navigationInterface.addItemHeader(self.tra("任务配置"), NavigationItemPosition.SCROLL)
        self.add_task_setting_pages()

        # ===== 高级设置 =====
        self.navigationInterface.addItemHeader(self.tra("高级设置"), NavigationItemPosition.SCROLL)
        self.add_settings_pages()

        # ===== 提示词管理 =====
        self.navigationInterface.addItemHeader(self.tra("提示词管理"), NavigationItemPosition.SCROLL)
        self.add_prompt_setting_pages()

        # ===== 公共表格 =====
        self.navigationInterface.addItemHeader(self.tra("公共表格"), NavigationItemPosition.SCROLL)
        self.add_table_pages()

        # 设置默认页面
        self.switchTo(self.edit_view_page)

        # 主题切换按钮
        self.theme_nav_button = NavigationPushButton(
            self._icon_for_mode(self._theme_mode), self.tra("主题切换"), False
        )
        self.navigationInterface.addWidget(
            routeKey="theme_navigation_button",
            widget=self.theme_nav_button,
            onClick=self.toggle_theme,
            position=NavigationItemPosition.BOTTOM,
        )

        # 应用设置按钮
        self.app_settings_page = AppSettingsPage("app_settings_page", self)
        self.addSubInterface(
            self.app_settings_page,
            FluentIcon.SETTING,
            self.tra("应用设置"),
            NavigationItemPosition.BOTTOM,
        )

        # 项目主页按钮
        avatar_path = str(resource_path("Logo", "Avatar.png"))
        self.navigationInterface.addWidget(
            routeKey="avatar_navigation_widget",
            widget=NavigationAvatarWidget("NEKOparapa", avatar_path),
            onClick=self.open_project_page,
            position=NavigationItemPosition.BOTTOM,
        )

    # 添加快速开始
    def add_project_pages(self, cache_manager, file_reader) -> None:
        self.platform_page = PlatformPage("platform_page", self)
        self.addSubInterface(self.platform_page, FluentIcon.IOT, self.tra("接口管理"), NavigationItemPosition.SCROLL)

        self.edit_view_page = EditViewPage("edit_view_page", self, cache_manager, file_reader)
        self.addSubInterface(self.edit_view_page, FluentIcon.PLAY, self.tra("开始翻译"), NavigationItemPosition.SCROLL)

    # 添加任务设置
    def add_task_setting_pages(self) -> None:
        self.task_settings_page = TaskSettingsPage("task_settings_page", self)
        self.addSubInterface(self.task_settings_page, FluentIcon.ZOOM, self.tra("任务设置"), NavigationItemPosition.SCROLL)
        self.output_settings_page = OutputSettingsPage("output_settings_page", self)
        self.addSubInterface(self.output_settings_page, FluentIcon.ALBUM, self.tra("输出设置"), NavigationItemPosition.SCROLL)

    # 添加翻译设置
    def add_settings_pages(self) -> None:
        self.translation_settings_page = TranslationSettingsPage("TranslationSettings", self)
        self.TranslationSettings = self.translation_settings_page
        self.addSubInterface(
            self.translation_settings_page,
            FluentIcon.EXPRESSIVE_INPUT_ENTRY,
            self.tra("翻译设置"),
            NavigationItemPosition.SCROLL,
        )

    # 添加提示词设置
    def add_prompt_setting_pages(self) -> None:
        self.prompt_optimization_navigation_item = BaseNavigationItem("prompt_optimization_navigation_item", self)
        self.addSubInterface(
            self.prompt_optimization_navigation_item,
            FluentIcon.BOOK_SHELF,
            self.tra("翻译提示词"),
            NavigationItemPosition.SCROLL,
        )

        # 翻译提示词
        self.system_prompt_page = SystemPromptPage("system_prompt_page", self)
        self.addSubInterface(self.system_prompt_page, FluentIcon.LABEL, self.tra("基础提示"), parent=self.prompt_optimization_navigation_item)
        self.characterization_prompt_page = CharacterizationPromptPage("characterization_prompt_page", self)
        self.addSubInterface(self.characterization_prompt_page, FluentIcon.PEOPLE, self.tra("角色介绍"), parent=self.prompt_optimization_navigation_item)
        self.world_building_prompt_page = WorldBuildingPromptPage("world_building_prompt_page", self)
        self.addSubInterface(self.world_building_prompt_page, FluentIcon.QUICK_NOTE, self.tra("背景设定"), parent=self.prompt_optimization_navigation_item)
        self.writing_style_prompt_page = WritingStylePromptPage("writing_style_prompt_page", self)
        self.addSubInterface(self.writing_style_prompt_page, FluentIcon.PENCIL_INK, self.tra("翻译风格"), parent=self.prompt_optimization_navigation_item)
        self.translation_example_prompt_page = TranslationExamplePromptPage("translation_example_prompt_page", self)
        self.addSubInterface(self.translation_example_prompt_page, FluentIcon.FIT_PAGE, self.tra("翻译示例"), parent=self.prompt_optimization_navigation_item)

        # 润色提示词
        self.polishing_prompt_navigation = BaseNavigationItem("polishing_prompt_navigation", self)
        self.addSubInterface(
            self.polishing_prompt_navigation,
            FluentIcon.PALETTE,
            self.tra("润色提示词"),
            NavigationItemPosition.SCROLL,
        )
        self.polishing_system_prompt_page = PolishingSystemPromptPage("polishing_system_prompt_page", self)
        self.addSubInterface(self.polishing_system_prompt_page, FluentIcon.LABEL, self.tra("基础提示"), parent=self.polishing_prompt_navigation)

    # 添加表格设置
    def add_table_pages(self) -> None:
        self.prompt_dictionary_page = PromptDictionaryPage("prompt_dictionary_page", self)
        self.addSubInterface(self.prompt_dictionary_page, FluentIcon.DICTIONARY, self.tra("术语表"), NavigationItemPosition.SCROLL)

        self.exclusion_list_page = ExclusionListPage("exclusion_list_page", self)
        self.addSubInterface(self.exclusion_list_page, FluentIcon.DICTIONARY, self.tra("禁翻表"), NavigationItemPosition.SCROLL)

        self.text_replace_navigation_item = BaseNavigationItem("text_replace_navigation_item", self)
        self.addSubInterface(self.text_replace_navigation_item, FluentIcon.FONT_SIZE, self.tra("文本替换"), NavigationItemPosition.SCROLL)

        self.text_replace_a_page = TextReplaceAPage("text_replace_a_page", self)
        self.addSubInterface(self.text_replace_a_page, FluentIcon.SEARCH, self.tra("译前替换"), parent=self.text_replace_navigation_item)

        self.text_replace_b_page = TextReplaceBPage("text_replace_b_page", self)
        self.addSubInterface(self.text_replace_b_page, FluentIcon.SEARCH_MIRROR, self.tra("译后替换"), parent=self.text_replace_navigation_item)
