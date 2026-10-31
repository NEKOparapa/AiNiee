import threading

import requests
from PyQt5.QtCore import QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QIcon
from PyQt5.QtWidgets import QAction, QApplication, QMenuBar
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    MessageBox,
    NavigationAvatarWidget,
    NavigationItemPosition,
    SystemThemeListener,
    Theme,
    setTheme,
    setThemeColor,
)

from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin
from Frontend.core.resources import frontend_resource_path
from Frontend.services.editor import PromptBuilderExtraction
from Frontend.services.backend_client import BackendError
from Frontend.platform.platform_paths import is_macos
from Frontend.core.log import LogMixin
from Frontend.app.navigation import BaseNavigationItem
from Frontend.pages.workspace.edit_view_page import EditViewPage
from Frontend.platform.macos import about_message, app_menu_title, command_shortcut
from Frontend.pages.providers.platform_page import PlatformPage
from Frontend.pages.prompts.extraction.extraction_prompt_page import ExtractionPromptPage
from Frontend.pages.prompts.polishing.polishing_system_prompt_page import PolishingSystemPromptPage
from Frontend.pages.logs.log_view_page import LogViewPage
from Frontend.pages.settings.advanced_settings_page import AdvancedSettingsPage
from Frontend.pages.settings.app_settings_page import AppSettingsPage
from Frontend.pages.settings.output_settings_page import OutputSettingsPage
from Frontend.pages.settings.task_settings_page import TaskSettingsPage
from Frontend.pages.tables.exclusion_list_page import ExclusionListPage
from Frontend.pages.tables.prompt_dictionary_page import PromptDictionaryPage
from Frontend.pages.tables.text_replace_a_page import TextReplaceAPage
from Frontend.pages.tables.text_replace_b_page import TextReplaceBPage
from Frontend.pages.prompts.translation.characterization_prompt_page import CharacterizationPromptPage
from Frontend.pages.prompts.translation.system_prompt_page import SystemPromptPage
from Frontend.pages.prompts.translation.translation_example_prompt_page import TranslationExamplePromptPage
from Frontend.pages.prompts.translation.world_building_prompt_page import WorldBuildingPromptPage
from Frontend.pages.prompts.translation.writing_style_prompt_page import WritingStylePromptPage
from Frontend.app.updates import UpdateCheckerThread, VersionManager
from Frontend.components.toast import ToastMixin


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
        self.default = self.get_default_section("AppFluentWindow")

        # 载入并保存默认配置
        config = self.initialize_config()

        # 更换界面显示的语言
        ConfigMixin.multilingual_interface_dict = self.load_translations(frontend_resource_path("localization"))
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
        self.setWindowIcon(QIcon(str(frontend_resource_path("icons", "Avatar.png"))))
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

    def switchTo(self, interface) -> None:
        current = self.stackedWidget.currentWidget()
        if current is not None and current is not interface:
            prepare_to_leave = getattr(current, "prepare_to_leave", None)
            if callable(prepare_to_leave) and not prepare_to_leave():
                self.navigationInterface.setCurrentItem(current.objectName())
                return
        super().switchTo(interface)

    # 窗口关闭函数
    def closeEvent(self, event) -> None:
        info_cont = self.tra("确定退出程序并关闭后端服务？\n后端将停止正在执行的任务并保存缓存。")
        message_box = MessageBox("Warning", info_cont, self)
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))

        if message_box.exec():
            current = self.stackedWidget.currentWidget()
            prepare_to_leave = getattr(current, "prepare_to_leave", None)
            if callable(prepare_to_leave) and not prepare_to_leave():
                event.ignore()
                return
            try:
                self.config_backend().shutdown()
            except BackendError as error:
                self.error(self.tra("关闭后端失败"), error=error)
                self.error_toast(self.tra("关闭后端失败"), str(error))
                event.ignore()
                return
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
            setTheme(Theme.AUTO)

    # 应用主题模式（auto/light/dark），由应用设置页的主题下拉调用
    def apply_theme_mode(self, mode: str) -> None:
        if mode == self._theme_mode:
            return
        self._theme_mode = mode
        setTheme(self._theme_for_mode(mode))
        self.save_config({"theme": mode})
        self.info_toast(self.tra("主题切换"), self._toast_for_mode(mode))

    @staticmethod
    def _theme_for_mode(mode: str) -> Theme:
        return {"light": Theme.LIGHT, "dark": Theme.DARK, "auto": Theme.AUTO}.get(mode, Theme.LIGHT)

    def _toast_for_mode(self, mode: str) -> str:
        return {
            "light": self.tra("已切换至浅色主题"),
            "dark": self.tra("已切换至深色主题"),
            "auto": self.tra("已切换至跟随系统"),
        }.get(mode, "")

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

        # ===== 提示词管理 =====
        self.navigationInterface.addItemHeader(self.tra("提示词管理"), NavigationItemPosition.SCROLL)
        self.add_prompt_setting_pages()

        # ===== 公共表格 =====
        self.navigationInterface.addItemHeader(self.tra("公共表格"), NavigationItemPosition.SCROLL)
        self.add_table_pages()

        # 设置默认页面
        self.switchTo(self.edit_view_page)

        # 运行日志按钮（在应用设置上方）
        self.log_view_page = LogViewPage("log_view_page", self)
        self.addSubInterface(
            self.log_view_page,
            FluentIcon.COMMAND_PROMPT,
            self.tra("运行日志"),
            NavigationItemPosition.BOTTOM,
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
        avatar_path = str(frontend_resource_path("icons", "Avatar.png"))
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

        self.advanced_settings_page = AdvancedSettingsPage("advanced_settings_page", self)
        self.TranslationSettings = self.advanced_settings_page.translation_settings_page
        self.addSubInterface(self.advanced_settings_page,FluentIcon.TILES,self.tra("高级设置"),NavigationItemPosition.SCROLL)

    # 添加提示词设置
    def add_prompt_setting_pages(self) -> None:
        # 提取提示词
        self.extraction_prompt_navigation = BaseNavigationItem("extraction_prompt_navigation", self)
        self.addSubInterface(
            self.extraction_prompt_navigation,
            FluentIcon.SEARCH,
            self.tra("提取提示词"),
            NavigationItemPosition.SCROLL,
        )
        self.extraction_system_prompt_page = ExtractionPromptPage(
            "extraction_system_prompt_page", self, PromptBuilderExtraction.BASIC
        )
        self.addSubInterface(
            self.extraction_system_prompt_page,
            FluentIcon.LABEL,
            self.tra("基础提示"),
            parent=self.extraction_prompt_navigation,
        )
        self.extraction_judgment_prompt_page = ExtractionPromptPage(
            "extraction_judgment_prompt_page", self, PromptBuilderExtraction.JUDGMENT
        )
        self.addSubInterface(
            self.extraction_judgment_prompt_page,
            FluentIcon.LABEL,
            self.tra("裁定提示"),
            parent=self.extraction_prompt_navigation,
        )

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
