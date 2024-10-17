from PyQt5.Qt import QIcon
from PyQt5.QtWidgets import QApplication

from qfluentwidgets import FluentIcon
from qfluentwidgets import FluentWindow
from qfluentwidgets import NavigationItemPosition

from .BaseNavigationItem import BaseNavigationItem

from .Project.ProjectPage import ProjectPage
from .Project.PlatformPage import PlatformPage

from .ApplicationSetting.BasicSettingsPage import BasicSettingsPage
from .ApplicationSetting.AdvanceSettingsPage import AdvanceSettingsPage
from .ApplicationSetting.PluginsSettingsPage import PluginsSettingsPage
from .ApplicationSetting.MixTranslationSettingsPage import MixTranslationSettingsPage

from .QualityOptimization.TextReplaceAPage import TextReplaceAPage
from .QualityOptimization.TextReplaceBPage import TextReplaceBPage
from .QualityOptimization.PromptDictionaryPage import PromptDictionaryPage
from .QualityOptimization.ModelArgumentsSakuraPage import ModelArgumentsSakuraPage
from .QualityOptimization.ModelArgumentsGooglePage import ModelArgumentsGooglePage
from .QualityOptimization.ModelArgumentsCoherePage import ModelArgumentsCoherePage
from .QualityOptimization.ModelArgumentsOpenAIPage import ModelArgumentsOpenAIPage
from .QualityOptimization.ModelArgumentsAnthropicPage import ModelArgumentsAnthropicPage
from .QualityOptimization.SystemPromptPage import SystemPromptPage
from .QualityOptimization.WritingStylePromptPage import WritingStylePromptPage
from .QualityOptimization.WorldBuildingPromptPage import WorldBuildingPromptPage
from .QualityOptimization.CharacterizationPromptPage import CharacterizationPromptPage
from .QualityOptimization.TranslationExamplePromptPage import TranslationExamplePromptPage

from .Start_Translation_Interface.Interface_start_translation import Widget_start_translation


class AppFluentWindow(FluentWindow): #主窗口

    APP_WIDTH = 1280
    APP_HEIGHT = 800

    def __init__(self, version):
        super().__init__()

        # 设置窗口属性
        self.resize(self.APP_WIDTH, self.APP_HEIGHT)
        self.setMinimumSize(self.APP_WIDTH, self.APP_HEIGHT)
        # self.setWindowIcon(QIcon(f":{configurator.resource_dir}/Avatar.png"))
        self.setWindowTitle(version)

        # 设置启动位置
        desktop = QApplication.desktop().availableGeometry()
        self.move(desktop.width()//2 - self.width()//2, desktop.height()//2 - self.height()//2)

        # 设置侧边栏宽度
        self.navigationInterface.setExpandWidth(256)

        # 侧边栏默认展开
        self.navigationInterface.setMinimumExpandWidth(self.APP_WIDTH)
        self.navigationInterface.expand(useAni = False)

    # 开始添加页面
    def add_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.add_project_pages(configurator, plugin_manager, background_executor, user_interface_prompter, jtpp)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_application_setting_pages(configurator, plugin_manager, background_executor, user_interface_prompter, jtpp)
        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)
        self.add_quality_optimization_pages(configurator, plugin_manager, background_executor, user_interface_prompter, jtpp)
        self.switchTo(self.Widget_start_translation)

    # 添加第一节
    def add_project_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.platform_page = PlatformPage("platform_page", self, configurator, background_executor)
        self.addSubInterface(self.platform_page, FluentIcon.IOT, "接口设置", NavigationItemPosition.SCROLL)
        self.prject_page = ProjectPage("prject_page", self, configurator)
        self.addSubInterface(self.prject_page, FluentIcon.FOLDER, "项目设置", NavigationItemPosition.SCROLL)
        
        self.Widget_start_translation = Widget_start_translation("Widget_start_translation", self, configurator, user_interface_prompter, background_executor)
        self.addSubInterface(self.Widget_start_translation, FluentIcon.PLAY, "开始翻译", NavigationItemPosition.SCROLL)
        
    # 添加第二节
    def add_application_setting_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.basic_settings_page = BasicSettingsPage("basic_settings_page", self, configurator)
        self.addSubInterface(self.basic_settings_page, FluentIcon.SETTING, "基础设置", NavigationItemPosition.SCROLL)
        self.advance_settings_page = AdvanceSettingsPage("advance_settings_page", self, configurator)
        self.addSubInterface(self.advance_settings_page, FluentIcon.ALBUM, "高级设置", NavigationItemPosition.SCROLL)
        self.plugins_settings_page = PluginsSettingsPage("plugins_settings_page", self, configurator, plugin_manager)
        self.addSubInterface(self.plugins_settings_page, FluentIcon.COMMAND_PROMPT, "插件设置", NavigationItemPosition.SCROLL)
        self.mix_translation_settings_page = MixTranslationSettingsPage("mix_translation_settings_page", self, configurator)
        self.addSubInterface(self.mix_translation_settings_page, FluentIcon.EMOJI_TAB_SYMBOLS, "混合翻译设置", NavigationItemPosition.SCROLL) 

    # 添加第三节
    def add_quality_optimization_pages(self, configurator, plugin_manager, background_executor, user_interface_prompter, jtpp):
        self.prompt_dictionary_page = PromptDictionaryPage("prompt_dictionary_page", self, configurator)
        self.addSubInterface(self.prompt_dictionary_page, FluentIcon.DICTIONARY, "指令词典", NavigationItemPosition.SCROLL)

        self.text_replace_navigation_item = BaseNavigationItem("text_replace_navigation_item", self)
        self.addSubInterface(self.text_replace_navigation_item, FluentIcon.LANGUAGE, "文本替换", NavigationItemPosition.SCROLL)
        self.text_replace_a_page = TextReplaceAPage("text_replace_a_page", self, configurator)
        self.addSubInterface(self.text_replace_a_page, FluentIcon.SEARCH, "译前替换", parent = self.text_replace_navigation_item) 
        self.text_replace_b_page = TextReplaceBPage("text_replace_b_page", self, configurator)
        self.addSubInterface(self.text_replace_b_page, FluentIcon.SEARCH_MIRROR, "译后替换", parent = self.text_replace_navigation_item) 

        self.prompt_optimization_navigation_item = BaseNavigationItem("prompt_optimization_navigation_item", self)
        self.addSubInterface(self.prompt_optimization_navigation_item, FluentIcon.BOOK_SHELF, "提示词优化", NavigationItemPosition.SCROLL)
        self.system_prompt_page = SystemPromptPage("system_prompt_page", self, configurator)
        self.addSubInterface(self.system_prompt_page, FluentIcon.LABEL, "基础指令", parent = self.prompt_optimization_navigation_item)
        self.characterization_prompt_page = CharacterizationPromptPage("characterization_prompt_page", self, configurator)
        self.addSubInterface(self.characterization_prompt_page, FluentIcon.EXPRESSIVE_INPUT_ENTRY, "角色介绍", parent = self.prompt_optimization_navigation_item)
        self.world_building_prompt_page = WorldBuildingPromptPage("world_building_prompt_page", self, configurator)
        self.addSubInterface(self.world_building_prompt_page, FluentIcon.QUICK_NOTE, "世界观设定", parent = self.prompt_optimization_navigation_item)
        self.writing_style_prompt_page = WritingStylePromptPage("writing_style_prompt_page", self, configurator)
        self.addSubInterface(self.writing_style_prompt_page, FluentIcon.PENCIL_INK, "行文措辞要求", parent = self.prompt_optimization_navigation_item)
        self.translation_example_prompt_page = TranslationExamplePromptPage("translation_example_prompt_page", self, configurator)
        self.addSubInterface(self.translation_example_prompt_page, FluentIcon.ZOOM, "翻译风格示例", parent = self.prompt_optimization_navigation_item)

        # 参数调整页面
        self.model_arguments_navigation_item = BaseNavigationItem("model_arguments_navigation_item", self)
        self.addSubInterface(self.model_arguments_navigation_item, FluentIcon.MIX_VOLUMES, "模型参数调整", NavigationItemPosition.SCROLL)
        self.model_arguments_sakura_page = ModelArgumentsSakuraPage("model_arguments_sakura_page", self, configurator)
        self.addSubInterface(self.model_arguments_sakura_page, FluentIcon.SPEED_OFF, "Sakura", parent = self.model_arguments_navigation_item)
        self.model_arguments_google_page = ModelArgumentsGooglePage("model_arguments_google_page", self, configurator)
        self.addSubInterface(self.model_arguments_google_page, FluentIcon.SPEED_OFF, "Google", parent = self.model_arguments_navigation_item)
        self.model_arguments_cohere_page = ModelArgumentsCoherePage("model_arguments_cohere_page", self, configurator)
        self.addSubInterface(self.model_arguments_cohere_page, FluentIcon.SPEED_OFF, "Cohere", parent = self.model_arguments_navigation_item)
        self.model_arguments_openai_page = ModelArgumentsOpenAIPage("model_arguments_openai_page", self, configurator)
        self.addSubInterface(self.model_arguments_openai_page, FluentIcon.SPEED_OFF, "OpenAI", parent = self.model_arguments_navigation_item)
        self.model_arguments_anthropic_page = ModelArgumentsAnthropicPage("model_arguments_anthropic_page", self, configurator)
        self.addSubInterface(self.model_arguments_anthropic_page, FluentIcon.SPEED_OFF, "Anthropic", parent = self.model_arguments_navigation_item)