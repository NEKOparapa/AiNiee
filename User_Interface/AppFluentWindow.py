from PyQt5.Qt import QUrl
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

from Base.AiNieeBase import AiNieeBase
from User_Interface.BaseNavigationItem import BaseNavigationItem
from User_Interface.Project.ProjectPage import ProjectPage
from User_Interface.Project.PlatformPage import PlatformPage
from User_Interface.Setting.BasicSettingsPage import BasicSettingsPage
from User_Interface.Setting.AdvanceSettingsPage import AdvanceSettingsPage
from User_Interface.Setting.PluginsSettingsPage import PluginsSettingsPage
from User_Interface.Setting.MixTranslationSettingsPage import MixTranslationSettingsPage
from User_Interface.Quality.TextReplaceAPage import TextReplaceAPage
from User_Interface.Quality.TextReplaceBPage import TextReplaceBPage
from User_Interface.Quality.PromptDictionaryPage import PromptDictionaryPage
from User_Interface.Quality.SystemPromptPage import SystemPromptPage
from User_Interface.Quality.WritingStylePromptPage import WritingStylePromptPage
from User_Interface.Quality.WorldBuildingPromptPage import WorldBuildingPromptPage
from User_Interface.Quality.CharacterizationPromptPage import CharacterizationPromptPage
from User_Interface.Quality.TranslationExamplePromptPage import TranslationExamplePromptPage
from User_Interface.App.AppSettingsPage import AppSettingsPage

# 旧页面
from User_Interface.Start_Translation_Interface.Interface_start_translation import Widget_start_translation

class AppFluentWindow(FluentWindow, AiNieeBase): #主窗口

    APP_WIDTH = 1280
    APP_HEIGHT = 800

    THEME_COLOR = "#8A95A9"
    
    DEFAULT = {
        "theme": "dark",
    }

    def __init__(self, version):
        super().__init__()

        # 载入配置文件
        config = self.load_config()

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

    # 重写窗口关闭函数
    def closeEvent(self, event):
        message_box = MessageBox("警告", "确定是否退出程序 ... ？", self)
        message_box.yesButton.setText("确认")
        message_box.cancelButton.setText("取消")

        if message_box.exec():
            self.info("主窗口已关闭，稍后应用将自动退出 ...")
            self.configurator.Running_status = 11
            event.accept()
        else:
            event.ignore()

    # 切换主题
    def toggle_theme(self):
        config = self.load_config()

        if not isDarkTheme():
            setTheme(Theme.DARK)
            config["theme"] = "dark"
        else:
            setTheme(Theme.LIGHT)
            config["theme"] = "light"

        config = self.save_config(config)

    # 打开主页
    def open_project_page(self):
        url = QUrl("https://github.com/NEKOparapa/AiNiee")
        QDesktopServices.openUrl(url)

    # 开始添加页面
    def add_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.add_project_pages(configurator, plugin_manager, background_executor, user_interface_prompter, jtpp)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_application_setting_pages(configurator, plugin_manager, background_executor, user_interface_prompter, jtpp)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_quality_optimization_pages(configurator, plugin_manager, background_executor, user_interface_prompter, jtpp)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_app_pages(configurator, plugin_manager, background_executor, user_interface_prompter, jtpp)

        # 设置默认页面
        self.switchTo(self.Widget_start_translation)
        
        # 主题切换按钮
        self.navigationInterface.addWidget(
            routeKey = "theme_navigation_button",
            widget = NavigationPushButton(
                FluentIcon.CONSTRACT,
                "变换自如",
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

        # 保存变量
        self.configurator = configurator

    # 添加第一节
    def add_project_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.platform_page = PlatformPage("platform_page", self, background_executor)
        self.addSubInterface(self.platform_page, FluentIcon.IOT, "接口管理", NavigationItemPosition.SCROLL)
        self.prject_page = ProjectPage("prject_page", self)
        self.addSubInterface(self.prject_page, FluentIcon.FOLDER, "项目设置", NavigationItemPosition.SCROLL)
        
        self.Widget_start_translation = Widget_start_translation("Widget_start_translation", self, configurator, user_interface_prompter, background_executor)
        self.addSubInterface(self.Widget_start_translation, FluentIcon.PLAY, "开始翻译", NavigationItemPosition.SCROLL)
        
    # 添加第二节
    def add_application_setting_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.basic_settings_page = BasicSettingsPage("basic_settings_page", self)
        self.addSubInterface(self.basic_settings_page, FluentIcon.SETTING, "基础设置", NavigationItemPosition.SCROLL)
        self.advance_settings_page = AdvanceSettingsPage("advance_settings_page", self)
        self.addSubInterface(self.advance_settings_page, FluentIcon.ALBUM, "高级设置", NavigationItemPosition.SCROLL)
        self.plugins_settings_page = PluginsSettingsPage("plugins_settings_page", self, plugin_manager)
        self.addSubInterface(self.plugins_settings_page, FluentIcon.COMMAND_PROMPT, "插件设置", NavigationItemPosition.SCROLL)
        self.mix_translation_settings_page = MixTranslationSettingsPage("mix_translation_settings_page", self)
        self.addSubInterface(self.mix_translation_settings_page, FluentIcon.EMOJI_TAB_SYMBOLS, "混合翻译设置", NavigationItemPosition.SCROLL) 

    # 添加第三节
    def add_quality_optimization_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.prompt_dictionary_page = PromptDictionaryPage("prompt_dictionary_page", self)
        self.addSubInterface(self.prompt_dictionary_page, FluentIcon.DICTIONARY, "指令词典", NavigationItemPosition.SCROLL)

        self.text_replace_navigation_item = BaseNavigationItem("text_replace_navigation_item", self)
        self.addSubInterface(self.text_replace_navigation_item, FluentIcon.LANGUAGE, "文本替换", NavigationItemPosition.SCROLL)
        self.text_replace_a_page = TextReplaceAPage("text_replace_a_page", self)
        self.addSubInterface(self.text_replace_a_page, FluentIcon.SEARCH, "译前替换", parent = self.text_replace_navigation_item) 
        self.text_replace_b_page = TextReplaceBPage("text_replace_b_page", self)
        self.addSubInterface(self.text_replace_b_page, FluentIcon.SEARCH_MIRROR, "译后替换", parent = self.text_replace_navigation_item) 

        self.prompt_optimization_navigation_item = BaseNavigationItem("prompt_optimization_navigation_item", self)
        self.addSubInterface(self.prompt_optimization_navigation_item, FluentIcon.BOOK_SHELF, "提示词优化", NavigationItemPosition.SCROLL)
        self.system_prompt_page = SystemPromptPage("system_prompt_page", self)
        self.addSubInterface(self.system_prompt_page, FluentIcon.LABEL, "基础指令", parent = self.prompt_optimization_navigation_item)
        self.characterization_prompt_page = CharacterizationPromptPage("characterization_prompt_page", self)
        self.addSubInterface(self.characterization_prompt_page, FluentIcon.EXPRESSIVE_INPUT_ENTRY, "角色介绍", parent = self.prompt_optimization_navigation_item)
        self.world_building_prompt_page = WorldBuildingPromptPage("world_building_prompt_page", self)
        self.addSubInterface(self.world_building_prompt_page, FluentIcon.QUICK_NOTE, "世界观设定", parent = self.prompt_optimization_navigation_item)
        self.writing_style_prompt_page = WritingStylePromptPage("writing_style_prompt_page", self)
        self.addSubInterface(self.writing_style_prompt_page, FluentIcon.PENCIL_INK, "行文措辞要求", parent = self.prompt_optimization_navigation_item)
        self.translation_example_prompt_page = TranslationExamplePromptPage("translation_example_prompt_page", self)
        self.addSubInterface(self.translation_example_prompt_page, FluentIcon.ZOOM, "翻译风格示例", parent = self.prompt_optimization_navigation_item)

    # 添加第四节
    def add_app_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.app_settings_page = AppSettingsPage("app_settings_page", self)
        self.addSubInterface(self.app_settings_page, FluentIcon.IOT, "应用设置", NavigationItemPosition.SCROLL)