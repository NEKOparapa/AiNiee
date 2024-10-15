import json
import os
import sys
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TeachingTip, TeachingTipTailPosition, TeachingTipView, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar

from .BaseNavigationItem import BaseNavigationItem

from .Project.ProjectPage import ProjectPage

from .ApplicationSetting.BasicSettingsPage import BasicSettingsPage
from .ApplicationSetting.AdvanceSettingsPage import AdvanceSettingsPage

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

from .AI_Platform_Interface.Interface_AI import Widget_AI
from .AI_Platform_Interface.Interface_Official_api import Widget_Official_api
from .AI_Platform_Interface.Interface_Openai import Widget_Openai
from .AI_Platform_Interface.Interface_Proxy import Widget_Proxy
from .AI_Platform_Interface.Interface_New_proxy import Widget_New_proxy
from .AI_Platform_Interface.Interface_Empty import Widget_Empty
from .AI_Platform_Interface.Interface_Anthropic import Widget_Anthropic
from .AI_Platform_Interface.Interface_Google import Widget_Google
from .AI_Platform_Interface.Interface_Cohere import Widget_Cohere
from .AI_Platform_Interface.Interface_ZhiPu import Widget_ZhiPu
from .AI_Platform_Interface.Interface_Yi import Widget_Yi
from .AI_Platform_Interface.Interface_Moonshot import Widget_Moonshot
from .AI_Platform_Interface.Interface_Deepseek import Widget_Deepseek
from .AI_Platform_Interface.Interface_Dashscope import Widget_Dashscope
from .AI_Platform_Interface.Interface_Volcengine import Widget_Volcengine
from .AI_Platform_Interface.Interface_SakuraLLM import Widget_SakuraLLM


from .Translation_Settings_Interface.Interface_translation_settings_C import Widget_translation_settings_C


from .Start_Translation_Interface.Interface_start_translation import Widget_start_translation


from .Other_Interfaces.Interface_AvatarWidget import AvatarWidget
from .Other_Interfaces.Interface_sponsor import Widget_sponsor

from .Text_Extraction_Tool_Interface.Interface_RPG import Widget_RPG
from .Text_Extraction_Tool_Interface.Interface_export_source_text import Widget_export_source_text
from .Text_Extraction_Tool_Interface.Interface_import_translated_text import Widget_import_translated_text
from .Text_Extraction_Tool_Interface.Interface_update_text import Widget_update_text



class window(FramelessWindow): #主窗口 v


    def __init__(self,Software_Version,configurator,user_interface_prompter,background_executor,jtpp):
        super().__init__()
        # use dark theme mode
        self.setTitleBar(StandardTitleBar(self))

        self.hBoxLayout = QHBoxLayout(self)
        self.navigationInterface = NavigationInterface(self, showMenuButton=True)
        self.stackWidget = QStackedWidget(self)

        # 版本号
        self.Software_Version = Software_Version

        self.configurator = configurator
        self.user_interface_prompter = user_interface_prompter
        self.background_executor = background_executor

        # 创建子界面控件，传入参数为对象名和parent

        # -----------------------------------------------------------
        # 第一节开始
        # -----------------------------------------------------------
        
        
        self.Widget_AI = Widget_AI('Widget_AI', self)
        self.Widget_Official_api = Widget_Official_api('Widget_Official_api', self)
        self.Widget_Openai = Widget_Openai('Widget_Openai', self,configurator,user_interface_prompter,background_executor)   
        self.Widget_Anthropic = Widget_Anthropic('Widget_Anthropic', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Google = Widget_Google('Widget_Google', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Cohere = Widget_Cohere('Widget_Cohere', self,configurator,user_interface_prompter,background_executor)
        self.Widget_ZhiPu = Widget_ZhiPu('Widget_ZhiPu', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Yi = Widget_Yi('Widget_Yi', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Moonshot = Widget_Moonshot('Widget_Moonshot', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Deepseek = Widget_Deepseek('Widget_Deepseek', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Dashscope = Widget_Dashscope('Widget_Dashscope', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Volcengine = Widget_Volcengine('Widget_Volcengine', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Proxy_platform = Widget_Empty('Widget_Proxy_platform', self)
        self.Widget_Proxy = Widget_Proxy('Widget_Proxy', self,configurator,user_interface_prompter,background_executor)
        self.Widget_Add_proxy_platform = Widget_Empty('Widget_Add_proxy_platform', self)
        self.Widget_SakuraLLM = Widget_SakuraLLM('Widget_SakuraLLM', self,configurator,user_interface_prompter,background_executor)


        self.Widget_start_translation = Widget_start_translation('Widget_start_translation', self,configurator,user_interface_prompter,background_executor)  


        # -----------------------------------------------------------
        # 第二节开始
        # -----------------------------------------------------------


        self.Widget_translation_settings_C = Widget_translation_settings_C('Widget_translation_settings_C', self,user_interface_prompter)  


        # -----------------------------------------------------------
        # 第三节开始
        # -----------------------------------------------------------


        # -----------------------------------------------------------
        # 第四节开始
        # -----------------------------------------------------------


        self.Widget_RPG = Widget_RPG('Widget_RPG', self)  
        self.Widget_export_source_text = Widget_export_source_text('Widget_export_source_text', self,configurator,user_interface_prompter,jtpp)  
        self.Widget_import_translated_text = Widget_import_translated_text('Widget_import_translated_text', self,configurator,user_interface_prompter,jtpp)  
        self.Widget_update_text = Widget_update_text('Widget_update_text', self,configurator,user_interface_prompter,jtpp)   


        # -----------------------------------------------------------
        # 第五节开始
        # -----------------------------------------------------------
        

        self.Widget_sponsor = Widget_sponsor('Widget_sponsor', self,configurator = self.configurator)


        self.initLayout() #调用初始化布局函数 
        self.initNavigation()   #调用初始化导航栏函数
        self.initWindow()  #调用初始化窗口函数


    # 初始化布局的函数
    def initLayout(self):   
        self.hBoxLayout.setSpacing(0)
        self.hBoxLayout.setContentsMargins(0, self.titleBar.height(), 0, 0)
        self.hBoxLayout.addWidget(self.navigationInterface)
        self.hBoxLayout.addWidget(self.stackWidget)
        self.hBoxLayout.setStretchFactor(self.stackWidget, 1)

    # 初始化导航栏的函数
    def initNavigation(self): # 详细介绍：https://pyqt-fluent-widgets.readthedocs.io/zh_CN/latest/navigation.html


        # -----------------------------------------------------------
        # 第一节开始
        # -----------------------------------------------------------


        # 添加账号设置界面
        self.addSubInterface(self.Widget_AI, FIF.IOT, '账号设置',NavigationItemPosition.SCROLL) # NavigationItemPosition.SCROLL表示在可滚动伸缩区域
        # 添加官方接口界面
        self.addSubInterface(self.Widget_Official_api, FIF.PEOPLE, '官方接口',parent=self.Widget_AI) # NavigationItemPosition.SCROLL表示在可滚动伸缩区域
        # 添加closeai官方账号界面
        self.addSubInterface(self.Widget_Openai, FIF.FEEDBACK, 'OpenAI',parent=self.Widget_Official_api) 
        # 添加谷歌官方账号界面
        self.addSubInterface(self.Widget_Google, FIF.FEEDBACK, 'Google',parent=self.Widget_Official_api)
        # 添加Cohere官方账号界面
        self.addSubInterface(self.Widget_Cohere, FIF.FEEDBACK, 'Cohere',parent=self.Widget_Official_api)
        # 添加anthropic官方账号界面
        self.addSubInterface(self.Widget_Anthropic, FIF.FEEDBACK, 'Anthropic',parent=self.Widget_Official_api)
        # 添加Moonshot官方账号界面
        self.addSubInterface(self.Widget_Moonshot, FIF.FEEDBACK, 'Moonshot',parent=self.Widget_Official_api) 
        # 添加Deepseek官方账号界面
        self.addSubInterface(self.Widget_Deepseek, FIF.FEEDBACK, 'Deepseek',parent=self.Widget_Official_api) 
        # 添加Dashscope官方账号界面
        self.addSubInterface(self.Widget_Dashscope, FIF.FEEDBACK, 'Dashscope',parent=self.Widget_Official_api) 
        # 添加Volcengine官方账号界面
        self.addSubInterface(self.Widget_Volcengine, FIF.FEEDBACK, 'Volcengine',parent=self.Widget_Official_api) 
        # 添加Yi官方账号界面
        self.addSubInterface(self.Widget_Yi, FIF.FEEDBACK, '零一万物',parent=self.Widget_Official_api) 
        # 添加智谱官方账号界面
        self.addSubInterface(self.Widget_ZhiPu, FIF.FEEDBACK, '智谱',parent=self.Widget_Official_api) 


        # 添加代理账号界面
        self.addSubInterface(self.Widget_Proxy_platform, FIF.CLOUD, '代理平台',parent=self.Widget_AI) 
        self.addSubInterface_add_new_proxy(self.Widget_Add_proxy_platform, FIF.ADD, '添加',parent=self.Widget_Proxy_platform) 
        self.addSubInterface(self.Widget_Proxy, FIF.CLOUD, '代理平台A',parent=self.Widget_Proxy_platform) 


        # 添加sakura界面
        self.addSubInterface(self.Widget_SakuraLLM, FIF.CONNECT, 'SakuraLLM',parent=self.Widget_AI) 

        self.prject_page = ProjectPage("prject_page", self, self.configurator)
        self.addSubInterface(self.prject_page, FIF.FOLDER, "项目设置", NavigationItemPosition.SCROLL) 
        self.addSubInterface(self.Widget_start_translation, FIF.PLAY, "开始翻译", NavigationItemPosition.SCROLL)

        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL) # 添加分隔符


        # -----------------------------------------------------------
        # 第二节开始
        # -----------------------------------------------------------

        self.basic_settings_page = BasicSettingsPage("basic_settings_page", self, self.configurator)
        self.addSubInterface(self.basic_settings_page, FIF.SETTING, "基础设置", NavigationItemPosition.SCROLL) 
        self.advance_settings_page = AdvanceSettingsPage("advance_settings_page", self, self.configurator)
        self.addSubInterface(self.advance_settings_page, FIF.ALBUM, "高级设置", NavigationItemPosition.SCROLL) 

        self.addSubInterface(self.Widget_translation_settings_C, FIF.EMOJI_TAB_SYMBOLS, "混合翻译设置", NavigationItemPosition.SCROLL)

        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL) # 添加分隔符


        # -----------------------------------------------------------
        # 第三节开始
        # -----------------------------------------------------------


        self.prompt_dictionary_page = PromptDictionaryPage("prompt_dictionary_page", self, self.configurator)
        self.addSubInterface(self.prompt_dictionary_page, FIF.DICTIONARY, "指令词典", NavigationItemPosition.SCROLL)

        self.text_replace_navigation_item = BaseNavigationItem("text_replace_navigation_item", self)
        self.addSubInterface(self.text_replace_navigation_item, FIF.LANGUAGE, "文本替换", NavigationItemPosition.SCROLL)
        self.text_replace_a_page = TextReplaceAPage("text_replace_a_page", self, self.configurator)
        self.addSubInterface(self.text_replace_a_page, FIF.SEARCH, "译前替换", parent = self.text_replace_navigation_item) 
        self.text_replace_b_page = TextReplaceBPage("text_replace_b_page", self, self.configurator)
        self.addSubInterface(self.text_replace_b_page, FIF.SEARCH_MIRROR, "译后替换", parent = self.text_replace_navigation_item) 

        self.prompt_optimization_navigation_item = BaseNavigationItem("prompt_optimization_navigation_item", self)
        self.addSubInterface(self.prompt_optimization_navigation_item, FIF.BOOK_SHELF, "提示词优化", NavigationItemPosition.SCROLL)
        self.system_prompt_page = SystemPromptPage("system_prompt_page", self, self.configurator)
        self.addSubInterface(self.system_prompt_page, FIF.LABEL, "基础指令", parent = self.prompt_optimization_navigation_item)
        self.characterization_prompt_page = CharacterizationPromptPage("characterization_prompt_page", self, self.configurator)
        self.addSubInterface(self.characterization_prompt_page, FIF.EXPRESSIVE_INPUT_ENTRY, "角色介绍", parent = self.prompt_optimization_navigation_item)
        self.world_building_prompt_page = WorldBuildingPromptPage("world_building_prompt_page", self, self.configurator)
        self.addSubInterface(self.world_building_prompt_page, FIF.QUICK_NOTE, "世界观设定", parent = self.prompt_optimization_navigation_item)
        self.writing_style_prompt_page = WritingStylePromptPage("writing_style_prompt_page", self, self.configurator)
        self.addSubInterface(self.writing_style_prompt_page, FIF.PENCIL_INK, "行文措辞要求", parent = self.prompt_optimization_navigation_item)
        self.translation_example_prompt_page = TranslationExamplePromptPage("translation_example_prompt_page", self, self.configurator)
        self.addSubInterface(self.translation_example_prompt_page, FIF.ZOOM, "翻译风格示例", parent = self.prompt_optimization_navigation_item)

        # 参数调整页面
        self.model_arguments_navigation_item = BaseNavigationItem("model_arguments_navigation_item", self)
        self.addSubInterface(self.model_arguments_navigation_item, FIF.MIX_VOLUMES, "模型参数调整", NavigationItemPosition.SCROLL)
        self.model_arguments_sakura_page = ModelArgumentsSakuraPage("model_arguments_sakura_page", self, self.configurator)
        self.addSubInterface(self.model_arguments_sakura_page, FIF.SPEED_OFF, "Sakura", parent = self.model_arguments_navigation_item) 
        self.model_arguments_google_page = ModelArgumentsGooglePage("model_arguments_google_page", self, self.configurator)
        self.addSubInterface(self.model_arguments_google_page, FIF.SPEED_OFF, "Google", parent = self.model_arguments_navigation_item) 
        self.model_arguments_cohere_page = ModelArgumentsCoherePage("model_arguments_cohere_page", self, self.configurator)
        self.addSubInterface(self.model_arguments_cohere_page, FIF.SPEED_OFF, "Cohere", parent = self.model_arguments_navigation_item) 
        self.model_arguments_openai_page = ModelArgumentsOpenAIPage("model_arguments_openai_page", self, self.configurator)
        self.addSubInterface(self.model_arguments_openai_page, FIF.SPEED_OFF, "OpenAI", parent = self.model_arguments_navigation_item) 
        self.model_arguments_anthropic_page = ModelArgumentsAnthropicPage("model_arguments_anthropic_page", self, self.configurator)
        self.addSubInterface(self.model_arguments_anthropic_page, FIF.SPEED_OFF, "Anthropic", parent = self.model_arguments_navigation_item) 
        

        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL)


        # -----------------------------------------------------------
        # 第四节开始
        # -----------------------------------------------------------


        # 添加RPG界面
        self.addSubInterface(self.Widget_RPG, FIF.TILES, 'StevExtraction',NavigationItemPosition.SCROLL)
        self.addSubInterface(self.Widget_export_source_text, FIF.SHARE, '提取原文',parent=self.Widget_RPG)
        self.addSubInterface(self.Widget_import_translated_text, FIF.LABEL, '导入译文',parent=self.Widget_RPG)
        self.addSubInterface(self.Widget_update_text, FIF.PIE_SINGLE, '提取增量文本',parent=self.Widget_RPG)

        self.navigationInterface.addSeparator(NavigationItemPosition.SCROLL) 

        # 添加赞助页面
        self.addSubInterface(self.Widget_sponsor, FIF.CAFE, '赞助一下', NavigationItemPosition.BOTTOM) 

        # 添加头像导航项
        self.navigationInterface.addWidget(
            routeKey='avatar',
            widget=AvatarWidget(configurator = self.configurator),
            onClick=self.showMessageBox,
            position=NavigationItemPosition.BOTTOM
        )

        # 展开状态下侧边导航的宽度
        self.navigationInterface.setExpandWidth(256)

        # 默认展示开始翻页页面
        self.stackWidget.setCurrentWidget(self.Widget_start_translation)
        self.stackWidget.currentChanged.connect(self.onCurrentInterfaceChanged)

    #初始化父窗口的函数
    def initWindow(self): 
        self.resize(1280, 800)
        self.setMinimumSize(1280, 800)
        #self.setWindowIcon(QIcon('resource/logo.png'))
        self.setWindowTitle(self.Software_Version)
        self.titleBar.setAttribute(Qt.WA_StyledBackground)

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)

        dir1 = os.path.join(self.configurator.resource_dir, "light")
        dir2 = os.path.join(dir1, "demo.qss")
        with open(dir2, encoding='utf-8') as f:
            self.setStyleSheet(f.read())

    # 添加界面到导航栏布局函数
    def addSubInterface(self, interface, icon, text: str, position=NavigationItemPosition.SCROLL, parent=None):
        """ add sub interface """
        self.stackWidget.addWidget(interface)
        self.navigationInterface.addItem(
            routeKey=interface.objectName(),
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(interface),
            position=position,
            tooltip=text,
            parentRouteKey=parent.objectName() if parent else None
        )

    # 添加新代理平台导航项函数
    def addSubInterface_add_new_proxy(self, interface, icon, text: str, position=NavigationItemPosition.SCROLL, parent=None):
        """ add sub interface """
        self.stackWidget.addWidget(interface)
        self.navigationInterface.addItem(
            routeKey=interface.objectName(),
            icon=icon,
            text=text,
            onClick=lambda: self.showTopTip(),
            position=position,
            tooltip=text,
            parentRouteKey=parent.objectName() if parent else None
        )



    # 前置弹窗函数
    def showTopTip(self):

        self.view = TeachingTipView(
            icon=None,
            title='Add a new platform',
            content="请输入新平台名字",
            #image='resource/Gyro.jpg',
            isClosable=True,
            tailPosition=TeachingTipTailPosition.RIGHT,
        )

        # 输入框
        self.TextEdit = LineEdit()
        self.TextEdit.setFixedWidth(300)


        # 按钮
        self.Button = PushButton('确认')
        self.Button.setFixedWidth(120)
        self.Button.clicked.connect(self.addSubInterface_onClick)
        
        # 添加到弹窗
        self.view.addWidget(self.TextEdit)
        self.view.addWidget(self.Button)

        self.w = TeachingTip.make(
            target=self.Widget_Add_proxy_platform,
            view=self.view,
            duration=-1,
            tailPosition=TeachingTipTailPosition.RIGHT,
            parent=self
        )
        self.view.closed.connect(self.w.close)



    # 添加新代理平台导航项辅助函数
    def addSubInterface_onClick(self):

        # 获取文本框内容，并确认是否为空
        text = self.TextEdit.text()
        if text == "":
            # 关闭弹窗
            self.w.close()

            return 0

        # 根据配置信息构建新的索引名,并更新配置信息
        if self.configurator.additional_platform_count >= 5: # 限制添加数量
            return 0
        
        # 获取未被使用的索引名
        object_name = self.check_keys_in_dict(self.configurator.additional_platform_dict)


        # 添加新的索引与名字
        self.configurator.additional_platform_count = self.configurator.additional_platform_count + 1
        self.configurator.additional_platform_dict[object_name] = text

        # 创建动态名实例,并存入全局字典里
        self.configurator.instances_information[object_name] = Widget_New_proxy(object_name, self,self.configurator,self.user_interface_prompter,self.background_executor)
        Widget_New = self.configurator.instances_information[object_name] 

        # 添加新导航项
        self.add_sub_interface(Widget_New,object_name,text)

        # 添加新选项到平台选项中
        self.user_interface_prompter.add_new_proxy_option(text)

        # 关闭弹窗
        self.w.close()

        # 重展开导航项，防止重叠显示
        self.navigationInterface.widget("Widget_Proxy_platform").setExpanded(False)
        self.navigationInterface.widget("Widget_Proxy_platform").setExpanded(True)

        self.navigationInterface.widget("Widget_AI").setExpanded(False)
        self.navigationInterface.widget("Widget_AI").setExpanded(True)



    # 添加新代理平台导航项函数
    def add_sub_interface(self, Widget_New,object_name,object_name_cn):

        # 添加新导航项
        self.stackWidget.addWidget( Widget_New)
        self.navigationInterface.addItem(
            routeKey=Widget_New.objectName(),
            icon=FIF.CLOUD,
            text=object_name_cn,
            onClick=lambda: self.switchTo(Widget_New),
            position=NavigationItemPosition.SCROLL,
            tooltip=object_name,
            parentRouteKey=self.Widget_Proxy_platform.objectName() if self.Widget_Proxy_platform else None
        )



    # 删除导航项
    def del_Interface(self,object_name):
        #
        self.navigationInterface.removeWidget(object_name)

        # 重展开导航项，防止重叠显示
        self.navigationInterface.widget("Widget_Proxy_platform").setExpanded(False)
        self.navigationInterface.widget("Widget_Proxy_platform").setExpanded(True)

        self.navigationInterface.widget("Widget_AI").setExpanded(False)
        self.navigationInterface.widget("Widget_AI").setExpanded(True)

    # 获取新的索引名
    def check_keys_in_dict(self, input_dict):
        for letter in ["Proxy_platform_B","Proxy_platform_C","Proxy_platform_D","Proxy_platform_E","Proxy_platform_F"]:
            if letter not in input_dict.keys():
                return letter
        return 0


    #切换到某个窗口的函数
    def switchTo(self, widget): 
        self.stackWidget.setCurrentWidget(widget) #设置堆栈窗口的当前窗口为widget

    #堆栈窗口的当前窗口改变时，调用的函数
    def onCurrentInterfaceChanged(self, index):    
        widget = self.stackWidget.widget(index)
        self.navigationInterface.setCurrentItem(widget.objectName())

    #头像导航项的函数调用的函数
    def showMessageBox(self):
        url = QUrl('https://github.com/NEKOparapa/AiNiee')
        QDesktopServices.openUrl(url)

    #窗口关闭函数，放在最后面，解决界面空白与窗口退出后子线程还在运行的问题
    def closeEvent(self, event):
        title = '确定是否退出程序?'
        content = """如果正在进行翻译任务，当前任务会取消。"""
        w = Dialog(title, content, self)

        if w.exec() :
            print("[INFO] 主窗口已经退出！")
            self.configurator.Running_status = 11
            event.accept()
        else:
            event.ignore()

