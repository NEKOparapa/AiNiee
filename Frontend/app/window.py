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
from Frontend.core.events import EventManager
from Frontend.core.icons import TaskSettingsIcon
from Frontend.core.resources import frontend_resource_path
from Frontend.services.backend_client import BackendError
from Frontend.platform.platform_paths import is_macos
from Frontend.core.log import LogMixin
from Frontend.app.navigation import BaseNavigationItem
from Frontend.pages.workspace.edit_view_page import EditViewPage
from Frontend.platform.macos import about_message, app_menu_title, command_shortcut
from Frontend.pages.providers.platform_page import PlatformPage
from Frontend.pages.providers.transcription_page import TranscriptionPage
from Frontend.pages.providers.image_generation_page import ImageGenerationPage
from Frontend.pages.media.workspace_page import ImageTranslationPage, AudioTranslationPage, VideoTranslationPage
from Frontend.pages.logs.log_view_page import LogViewPage
from Frontend.pages.settings.app_settings_page import AppSettingsPage
from Frontend.pages.settings.audio_translation_settings_page import AudioTranslationSettingsPage
from Frontend.pages.settings.video_translation_settings_page import VideoTranslationSettingsPage
from Frontend.pages.settings.image_translation_settings_page import ImageTranslationSettingsPage
from Frontend.pages.settings.text_settings_page import TextSettingsPage
from Frontend.pages.tables.exclusion_list_page import ExclusionListPage
from Frontend.pages.tables.prompt_dictionary_page import PromptDictionaryPage
from Frontend.pages.tables.text_replace_a_page import TextReplaceAPage
from Frontend.pages.tables.text_replace_b_page import TextReplaceBPage
from Frontend.app.updates import UpdateCheckerThread, VersionManager
from Frontend.components.toast import ToastMixin


# 主窗口
class AppFluentWindow(FluentWindow, ConfigMixin, LogMixin, ToastMixin, Base):
    APP_WIDTH = 1600
    APP_HEIGHT = 900
    THEME_COLOR = "#808b9d"

    def __init__(self, version: str, cache_manager, file_reader) -> None:
        super().__init__()
        self._close_in_progress = False
        self._shutdown_complete = False

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
        language = config.get("interface_language_setting")
        ConfigMixin.current_interface_language = (
            language if language in self.INTERFACE_LANGUAGES else self.INTERFACE_LANGUAGES[0]
        )
        self.info(f"Current Interface Language: {ConfigMixin.current_interface_language}")

        # 设置主题颜色与主题
        self._theme_mode = config.get("theme", "auto")
        setThemeColor(config.get("accent_color", self.THEME_COLOR))
        setTheme(self._theme_for_mode(self._theme_mode))

        self.systemThemeListener = SystemThemeListener(self)
        self.systemThemeListener.systemThemeChanged.connect(self._on_system_theme_changed)
        self.systemThemeListener.start()

        # 为侧边栏和原文、译文并排显示预留更多横向空间。
        desktop = QApplication.desktop().availableGeometry()
        initial_width = int(desktop.width() * 0.9)
        initial_height = int(desktop.height() * 0.9)
        self.resize(initial_width, initial_height)
        self.setWindowTitle(version)
        self.setWindowIcon(QIcon(str(frontend_resource_path("icons", "Avatar.png"))))
        self.titleBar.iconLabel.hide()

        # 初始化版本管理器，并在应用加载完成后异步检查更新
        self.version_manager = VersionManager(self, version)
        QTimer.singleShot(3000, self.check_for_updates)

        # 设置启动位置
        self.move(
            desktop.x() + (desktop.width() - self.width()) // 2,
            desktop.y() + (desktop.height() - self.height()) // 2,
        )

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
        if self._shutdown_complete:
            event.accept()
            return
        if self._close_in_progress:
            event.ignore()
            return
        self._close_in_progress = True
        try:
            for page in getattr(self, "media_pages", ()):
                if not page.prepare_to_close():
                    event.ignore()
                    return
            info_cont = self.tra("确定退出程序并关闭后端服务？\n后端将停止正在执行的任务并保存缓存。")
            message_box = MessageBox("Warning", info_cont, self)
            message_box.yesButton.setText(self.tra("确认"))
            message_box.cancelButton.setText(self.tra("取消"))

            if not message_box.exec():
                event.ignore()
                return
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

            # A native Alt+F4 may send a QCloseEvent without calling QWidget.close.
            # Commit shutdown once, including when another close event is queued.
            self._shutdown_complete = True
            for page in getattr(self, "media_pages", ()):
                page.cleanup()
            try:
                # Local cleanup must run before quitting the Qt event loop.
                EventManager.get_singleton().process_event(Base.EVENT.APP_SHUT_DOWN, {})
            except Exception as error:
                self.error("关闭前端组件时发生错误", error=error)
            try:
                self._stop_theme_listener()
            except Exception as error:
                self.error("停止系统主题监听时发生错误", error=error)
            self.info(self.tra("主窗口已关闭，稍后应用将自动退出") + " ... ")
            event.accept()
            self.hide()
            application = QApplication.instance()
            if application is not None:
                QTimer.singleShot(0, application.quit)
        finally:
            self._close_in_progress = False

    def _stop_theme_listener(self) -> None:
        # deleteLater destroys the C++ object, not its Python attribute. Remove
        # our reference first so repeated cleanup never touches a stale wrapper.
        listener = self.__dict__.pop("systemThemeListener", None)
        if listener is None:
            return
        try:
            listener.requestInterruption()
            listener.quit()
            if not listener.wait(100):
                # On Windows darkdetect blocks in the registry notification API
                # and does not observe QThread's cooperative interruption flag.
                listener.terminate()
                if not listener.wait(2000):
                    self.warning("系统主题监听线程未及时结束")
                    return
            listener.deleteLater()
        except RuntimeError as error:
            if not EventManager._is_deleted_qobject_error(error):
                raise

    def _on_system_theme_changed(self) -> None:
        if self._theme_mode == "auto":
            setTheme(Theme.AUTO)

    # 应用设置页在保存成功后调用；其他入口默认先保存再切换。
    def apply_theme_mode(self, mode: str, *, persist: bool = True) -> None:
        if mode == self._theme_mode:
            return
        if persist:
            self.save_config({"theme": mode})
        self._theme_mode = mode
        setTheme(self._theme_for_mode(mode))
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
        # 接口管理位于快速开始分组上方。
        self.add_project_pages(cache_manager, file_reader)

        # ===== 任务配置 =====
        self.navigationInterface.addItemHeader(self.tra("任务配置"), NavigationItemPosition.SCROLL)
        self.add_task_setting_pages()

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

    # 添加接口配置与快速开始
    def add_project_pages(self, cache_manager, file_reader) -> None:
        self.navigationInterface.addItemHeader(self.tra("接口配置"), NavigationItemPosition.SCROLL)
        self.interface_management_navigation = BaseNavigationItem("interface_management_navigation", self)
        self.interface_management_item = self.addSubInterface(
            self.interface_management_navigation,
            FluentIcon.IOT,
            self.tra("接口管理"),
            NavigationItemPosition.SCROLL,
        )
        self.platform_page = PlatformPage("platform_page", self)
        self.platform_page.header_card.titleLabel.setText(self.tra("翻译接口"))
        self.addSubInterface(
            self.platform_page, self.platform_page.ICON, self.tra("翻译接口"),
            parent=self.interface_management_navigation,
        )
        self.transcription_page = TranscriptionPage("transcription_page", self)
        self.addSubInterface(
            self.transcription_page, self.transcription_page.ICON, self.tra("转录接口"),
            parent=self.interface_management_navigation,
        )
        self.image_generation_page = ImageGenerationPage("image_generation_page", self)
        self.addSubInterface(
            self.image_generation_page, self.image_generation_page.ICON, self.tra("生图接口"),
            parent=self.interface_management_navigation,
        )

        self.navigationInterface.addItemHeader(self.tra("快速开始"), NavigationItemPosition.SCROLL)
        self.edit_view_page = EditViewPage("edit_view_page", self, cache_manager, file_reader)
        self.addSubInterface(self.edit_view_page, FluentIcon.DOCUMENT, self.tra("文本翻译"), NavigationItemPosition.SCROLL)
        self.image_translation_page = ImageTranslationPage(parent=self)
        self.audio_translation_page = AudioTranslationPage(parent=self)
        self.video_translation_page = VideoTranslationPage(parent=self)
        self.media_pages = (self.image_translation_page, self.audio_translation_page, self.video_translation_page)
        self.addSubInterface(self.image_translation_page, FluentIcon.PHOTO, self.tra("图片翻译"), NavigationItemPosition.SCROLL)
        self.addSubInterface(self.audio_translation_page, FluentIcon.MUSIC, self.tra("音频翻译"), NavigationItemPosition.SCROLL)
        self.addSubInterface(self.video_translation_page, FluentIcon.VIDEO, self.tra("视频翻译"), NavigationItemPosition.SCROLL)

    # 添加任务设置
    def add_task_setting_pages(self) -> None:
        self.text_translation_settings_navigation = BaseNavigationItem("text_translation_settings_navigation", self)
        self.text_translation_settings_item = self.addSubInterface(
            self.text_translation_settings_navigation,
            TaskSettingsIcon.TEXT,
            self.tra("文译设置"),
            NavigationItemPosition.SCROLL,
        )
        self.extraction_settings_page = TextSettingsPage("extraction_settings_page", self, stage="extraction")
        self.addSubInterface(
            self.extraction_settings_page, FluentIcon.SEARCH, self.tra("提取设置"),
            parent=self.text_translation_settings_navigation,
        )
        self.translation_settings_page = TextSettingsPage("translation_settings_page", self, stage="translation")
        self.addSubInterface(
            self.translation_settings_page, FluentIcon.EDIT, self.tra("翻译设置"),
            parent=self.text_translation_settings_navigation,
        )

        self.add_image_translation_setting_pages()

        self.audio_translation_settings_page = AudioTranslationSettingsPage("audio_translation_settings_page", self)
        self.addSubInterface(
            self.audio_translation_settings_page, TaskSettingsIcon.AUDIO,
            self.tra("音译设置"), NavigationItemPosition.SCROLL,
        )
        self.video_translation_settings_page = VideoTranslationSettingsPage("video_translation_settings_page", self)
        self.addSubInterface(self.video_translation_settings_page, TaskSettingsIcon.VIDEO,
                             self.tra("视译设置"), NavigationItemPosition.SCROLL)

    def add_image_translation_setting_pages(self) -> None:
        self.image_translation_settings_page = ImageTranslationSettingsPage("image_translation_settings_page", self)
        self.image_translation_settings_item = self.addSubInterface(
            self.image_translation_settings_page, TaskSettingsIcon.IMAGE,
            self.tra("图译设置"), NavigationItemPosition.SCROLL,
        )

    # 添加表格设置
    def add_table_pages(self) -> None:
        self.prompt_dictionary_page = PromptDictionaryPage("prompt_dictionary_page", self)
        self.addSubInterface(self.prompt_dictionary_page, FluentIcon.DICTIONARY, self.tra("术语表"), NavigationItemPosition.SCROLL)

        self.exclusion_list_page = ExclusionListPage("exclusion_list_page", self)
        self.addSubInterface(self.exclusion_list_page, FluentIcon.DICTIONARY, self.tra("禁翻表"), NavigationItemPosition.SCROLL)

        self.text_replace_navigation_item = BaseNavigationItem("text_replace_navigation_item", self)
        self.addSubInterface(self.text_replace_navigation_item, FluentIcon.FONT, self.tra("文本替换"), NavigationItemPosition.SCROLL)

        self.text_replace_a_page = TextReplaceAPage("text_replace_a_page", self)
        self.addSubInterface(self.text_replace_a_page, FluentIcon.SEARCH, self.tra("译前替换"), parent=self.text_replace_navigation_item)

        self.text_replace_b_page = TextReplaceBPage("text_replace_b_page", self)
        self.addSubInterface(self.text_replace_b_page, FluentIcon.SEARCH_MIRROR, self.tra("译后替换"), parent=self.text_replace_navigation_item)
