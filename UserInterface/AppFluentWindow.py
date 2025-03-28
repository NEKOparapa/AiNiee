from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication

from qfluentwidgets import Theme
from qfluentwidgets import setTheme
from qfluentwidgets import isDarkTheme
from qfluentwidgets import setThemeColor
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import FluentWindow
from qfluentwidgets import NavigationPushButton
from qfluentwidgets import NavigationItemPosition
from qfluentwidgets import NavigationAvatarWidget

from Base.Base import Base
from Base.PluginManager import PluginManager

from UserInterface.AppSettingsPage import AppSettingsPage
from UserInterface.BaseNavigationItem import BaseNavigationItem
from UserInterface.Platform.PlatformPage import PlatformPage

from UserInterface.Monitoring.TranslationPage import TranslationPage

from UserInterface.Setting.ProjectSettingsPage import ProjectSettingsPage
from UserInterface.Setting.BasicSettingsPage import BasicSettingsPage
from UserInterface.Setting.AdvanceSettingsPage import AdvanceSettingsPage
from UserInterface.Setting.PluginsSettingsPage import PluginsSettingsPage

from UserInterface.DRSetting.FlowDesignPage import FlowDesignPage
from UserInterface.DRSetting.FlowBasicSettingsPage import FlowBasicSettingsPage

from UserInterface.Table.TextReplaceAPage import TextReplaceAPage
from UserInterface.Table.TextReplaceBPage import TextReplaceBPage
from UserInterface.Table.PromptDictionaryPage import PromptDictionaryPage
from UserInterface.Table.ExclusionListPage import ExclusionListPage

from UserInterface.Quality.SystemPromptPage import SystemPromptPage
from UserInterface.Quality.WritingStylePromptPage import WritingStylePromptPage
from UserInterface.Quality.WorldBuildingPromptPage import WorldBuildingPromptPage
from UserInterface.Quality.CharacterizationPromptPage import CharacterizationPromptPage
from UserInterface.Quality.TranslationExamplePromptPage import TranslationExamplePromptPage


from StevExtraction import jtpp
from UserInterface.Extraction_Tool.Export_Source_Text import Widget_export_source_text
from UserInterface.Extraction_Tool.Import_Translated_Text import Widget_import_translated_text
from UserInterface.Extraction_Tool.Export_Update_Text import Widget_update_text

class AppFluentWindow(FluentWindow, Base): #主窗口

    APP_WIDTH = 1280
    APP_HEIGHT = 800

    THEME_COLOR = "#8A95A9"

    def __init__(self, version: str, plugin_manager: PluginManager) -> None:
        super().__init__()

        # 默认配置
        self.default = {
            "theme": "dark",
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 更换界面显示的语言
        Base.multilingual_interface_dict = self.load_translations(Base.translation_json_file) # 读取多语言文本
        current_language = config.get("interface_language_setting","简中") # 读取界面语言设置
        Base.current_interface_language = current_language  # 根据配置改变全局界面语言设定
        self.info(f"Current Interface Language: {Base.current_interface_language}") # 打印当前语言，方便调试

        # 打印日志
        if self.is_debug():
            self.info("Debug mode is enabled ...")

        # 设置主题颜色
        setThemeColor(self.THEME_COLOR)

        # 设置主题
        setTheme(Theme.DARK if config.get("theme") == "dark" else Theme.LIGHT)

        # 设置窗口属性
        self.resize(self.APP_WIDTH, self.APP_HEIGHT)
        self.setMinimumSize(self.APP_WIDTH, self.APP_HEIGHT)
        self.setWindowTitle(version)
        self.titleBar.iconLabel.hide()

        # 设置启动位置
        desktop = QApplication.desktop().availableGeometry()
        self.move(desktop.width()//2 - self.width()//2, desktop.height()//2 - self.height()//2)

        # 设置侧边栏宽度
        self.navigationInterface.setExpandWidth(256)

        # 侧边栏默认展开
        self.navigationInterface.setMinimumExpandWidth(self.APP_WIDTH)
        self.navigationInterface.expand(useAni = False)

        # 隐藏返回按钮
        self.navigationInterface.panel.setReturnButtonVisible(False)

        # 添加页面
        self.add_pages(plugin_manager)

    # 重写窗口关闭函数
    def closeEvent(self, event) -> None:
        info_cont = self.tra("确定是否退出程序") + " ... ？"
        message_box = MessageBox("Warning", info_cont, self)
        message_box.yesButton.setText(self.tra("确认"))
        message_box.cancelButton.setText(self.tra("取消"))

        if message_box.exec():
            self.emit(Base.EVENT.APP_SHUT_DOWN, {})
            info_cont = self.tra("主窗口已关闭，稍后应用将自动退出") + " ... "
            self.info(info_cont)
            event.accept()
        else:
            event.ignore()

    # 切换主题
    def toggle_theme(self) -> None:
        config = self.load_config()

        if not isDarkTheme():
            setTheme(Theme.DARK)
            config["theme"] = "dark"
        else:
            setTheme(Theme.LIGHT)
            config["theme"] = "light"

        config = self.save_config(config)

    # 打开主页
    def open_project_page(self) -> None:
        url = QUrl("https://github.com/NEKOparapa/AiNiee")
        QDesktopServices.openUrl(url)

    # 开始添加页面
    def add_pages(self, plugin_manager: PluginManager) -> None:
        self.add_project_pages(plugin_manager)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_setting_pages(plugin_manager)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_double_request_pages(plugin_manager)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_quality_pages(plugin_manager)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_stev_extraction_pages(plugin_manager)

        # 设置默认页面
        self.switchTo(self.translation_page)

        # 应用设置按钮
        self.app_settings_page = AppSettingsPage("app_settings_page", self)
        self.addSubInterface(self.app_settings_page, FluentIcon.SETTING, self.tra("应用设置"), NavigationItemPosition.BOTTOM)

        # 主题切换按钮
        self.navigationInterface.addWidget(
            routeKey = "theme_navigation_button",
            widget = NavigationPushButton(
                FluentIcon.CONSTRACT,
                self.tra("主题切换"),
                False
            ),
            onClick = self.toggle_theme,
            position = NavigationItemPosition.BOTTOM
        )

        # 项目主页按钮
        self.navigationInterface.addWidget(
            routeKey = "avatar_navigation_widget",
            widget = NavigationAvatarWidget(
                "NEKOparapa",
                "Resource/Avatar.png",
            ),
            onClick = self.open_project_page,
            position = NavigationItemPosition.BOTTOM
        )

    # 添加第一节
    def add_project_pages(self, plugin_manager: PluginManager) -> None:
        self.platform_page = PlatformPage("platform_page", self)
        self.addSubInterface(self.platform_page, FluentIcon.IOT, self.tra("接口管理"), NavigationItemPosition.SCROLL)
        self.prject_page = ProjectSettingsPage("ProjectSettingsPagee", self)
        self.addSubInterface(self.prject_page, FluentIcon.FOLDER, self.tra("项目设置"), NavigationItemPosition.SCROLL)
        self.translation_page = TranslationPage("translation_page", self)
        self.addSubInterface(self.translation_page, FluentIcon.PLAY, self.tra("开始翻译"), NavigationItemPosition.SCROLL)

    # 添加第二节
    def add_setting_pages(self, plugin_manager: PluginManager) -> None:
        self.basic_settings_page = BasicSettingsPage("basic_settings_page", self)
        self.addSubInterface(self.basic_settings_page, FluentIcon.ZOOM, self.tra("基础设置"), NavigationItemPosition.SCROLL)
        self.advance_settings_page = AdvanceSettingsPage("advance_settings_page", self)
        self.addSubInterface(self.advance_settings_page, FluentIcon.ALBUM, self.tra("高级设置"), NavigationItemPosition.SCROLL)
        self.plugins_settings_page = PluginsSettingsPage("plugins_settings_page", self, plugin_manager)
        self.addSubInterface(self.plugins_settings_page, FluentIcon.COMMAND_PROMPT, self.tra("插件设置"), NavigationItemPosition.SCROLL)
        self.prompt_optimization_navigation_item = BaseNavigationItem("prompt_optimization_navigation_item", self)
        self.addSubInterface(self.prompt_optimization_navigation_item, FluentIcon.BOOK_SHELF, self.tra("提示词设置"), NavigationItemPosition.SCROLL)
        self.system_prompt_page = SystemPromptPage("system_prompt_page", self)
        self.addSubInterface(self.system_prompt_page, FluentIcon.LABEL, self.tra("基础提示"), parent = self.prompt_optimization_navigation_item)
        self.characterization_prompt_page = CharacterizationPromptPage("characterization_prompt_page", self)
        self.addSubInterface(self.characterization_prompt_page, FluentIcon.EXPRESSIVE_INPUT_ENTRY, self.tra("角色介绍"), parent = self.prompt_optimization_navigation_item)
        self.world_building_prompt_page = WorldBuildingPromptPage("world_building_prompt_page", self)
        self.addSubInterface(self.world_building_prompt_page, FluentIcon.QUICK_NOTE, self.tra("背景设定"), parent = self.prompt_optimization_navigation_item)
        self.writing_style_prompt_page = WritingStylePromptPage("writing_style_prompt_page", self)
        self.addSubInterface(self.writing_style_prompt_page, FluentIcon.PENCIL_INK, self.tra("翻译风格"), parent = self.prompt_optimization_navigation_item)
        self.translation_example_prompt_page = TranslationExamplePromptPage("translation_example_prompt_page", self)
        self.addSubInterface(self.translation_example_prompt_page, FluentIcon.FIT_PAGE, self.tra("翻译示例"), parent = self.prompt_optimization_navigation_item)

    # 添加第三节
    def add_double_request_pages(self, plugin_manager: PluginManager) -> None:
        self.double_request_settings_page = BaseNavigationItem("double_request_settings_page", self)
        self.addSubInterface(self.double_request_settings_page, FluentIcon.TILES, self.tra("双子星翻译"), NavigationItemPosition.SCROLL)
        self.flow_basic_settings_page =FlowBasicSettingsPage("flow_basic_settings_page", self)
        self.addSubInterface(self.flow_basic_settings_page, FluentIcon.ZOOM, self.tra("基础设置"), parent = self.double_request_settings_page)
        self.flow_design_page =FlowDesignPage("flow_design_page", self)
        self.addSubInterface(self.flow_design_page, FluentIcon.VIDEO, self.tra("流程设计"), parent = self.double_request_settings_page)


    # 添加第四节
    def add_quality_pages(self, plugin_manager: PluginManager) -> None:
        self.prompt_dictionary_page = PromptDictionaryPage("prompt_dictionary_page", self)
        self.addSubInterface(self.prompt_dictionary_page, FluentIcon.DICTIONARY, self.tra("术语表"), NavigationItemPosition.SCROLL)
        self.exclusion_list_page = ExclusionListPage("exclusion_list_page", self)
        self.addSubInterface(self.exclusion_list_page, FluentIcon.DICTIONARY, self.tra("禁翻表"), NavigationItemPosition.SCROLL)
        self.text_replace_navigation_item = BaseNavigationItem("text_replace_navigation_item", self)
        self.addSubInterface(self.text_replace_navigation_item, FluentIcon.FONT_SIZE, self.tra("文本替换"), NavigationItemPosition.SCROLL)
        self.text_replace_a_page = TextReplaceAPage("text_replace_a_page", self)
        self.addSubInterface(self.text_replace_a_page, FluentIcon.SEARCH, self.tra("译前替换"), parent = self.text_replace_navigation_item)
        self.text_replace_b_page = TextReplaceBPage("text_replace_b_page", self)
        self.addSubInterface(self.text_replace_b_page, FluentIcon.SEARCH_MIRROR, self.tra("译后替换"), parent = self.text_replace_navigation_item)



    # 添加第五节
    def add_stev_extraction_pages(self, plugin_manager: PluginManager) -> None:
        self.stev_extraction_navigation_item = BaseNavigationItem("stev_extraction_navigation_item", self)
        self.addSubInterface(self.stev_extraction_navigation_item, FluentIcon.ZIP_FOLDER, self.tra("StevExtraction"), NavigationItemPosition.SCROLL)
        self.widget_export_source_text = Widget_export_source_text("widget_export_source_text", self, jtpp)
        self.addSubInterface(self.widget_export_source_text, FluentIcon.SHARE, self.tra("导出文本"), parent = self.stev_extraction_navigation_item)
        self.widget_import_translated_text = Widget_import_translated_text("widget_import_translated_text", self, jtpp)
        self.addSubInterface(self.widget_import_translated_text, FluentIcon.DOWNLOAD, self.tra("导入文本"), parent = self.stev_extraction_navigation_item)
        self.widget_update_text = Widget_update_text("widget_update_text", self, jtpp)
        self.addSubInterface(self.widget_update_text, FluentIcon.UPDATE, self.tra("导出增量文本"), parent = self.stev_extraction_navigation_item)