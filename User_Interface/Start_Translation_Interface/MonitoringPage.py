from PyQt5.QtCore import QEasingCurve
from PyQt5.QtWidgets import QFrame, QGroupBox, QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import Action, FlowLayout, PrimaryPushButton, PushButton
from qfluentwidgets import FluentIcon
from qfluentwidgets import MessageBox
from qfluentwidgets import PlainTextEdit

from Base.AiNieeBase import AiNieeBase
from Widget.CommandBarCard import CommandBarCard
from Widget.ProjectTypeCard import ProjectTypeCard
from Widget.TranslationSpeedCard import TranslationSpeedCard

class MonitoringPage(QFrame, AiNieeBase):

    def __init__(self, text: str, window,configurator=None,background_executor=None):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        self.configurator = configurator
        self.background_executor = background_executor


        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下


        # 设置监控卡片容器
        self.card_layout = FlowLayout(self, needAni=True)  # 启用动画
        self.card_layout.setAnimation(250, QEasingCurve.OutQuad)        # 自定义动画参数
        self.card_layout.setContentsMargins(30, 30, 30, 30)
        self.card_layout.setVerticalSpacing(20)
        self.card_layout.setHorizontalSpacing(10)

        # 添加监控卡片
        self.ProjectTypeCard =  ProjectTypeCard(self)
        self.card_layout.addWidget(self.ProjectTypeCard)

        # 添加监控卡片
        self.TranslationSpeedCard =  TranslationSpeedCard(self)
        self.card_layout.addWidget(self.TranslationSpeedCard)



        # -----创建第x个组，添加多个组件-----
        box_start_translation = QGroupBox()
        box_start_translation.setStyleSheet(""" QGroupBox {border: 0px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_start_translation = QHBoxLayout()


        #设置“开始翻译”的按钮
        self.primaryButton_start_translation = PrimaryPushButton('开始翻译', self, FluentIcon.PLAY)
        self.primaryButton_start_translation.clicked.connect(self.Start_translation) #按钮绑定槽函数


        #设置“暂停翻译”的按钮
        self.primaryButton_pause_translation = PrimaryPushButton('暂停翻译', self, FluentIcon.PAUSE)
        self.primaryButton_pause_translation.clicked.connect(self.pause_translation) #按钮绑定槽函数
        #隐藏按钮
        self.primaryButton_pause_translation.hide()

        #设置“继续翻译”的按钮
        self.primaryButton_continue_translation = PrimaryPushButton('继续翻译', self, FluentIcon.ROTATE)
        self.primaryButton_continue_translation.clicked.connect(self.continue_translation) #按钮绑定槽函数
        #隐藏按钮
        self.primaryButton_continue_translation.hide()


        #设置“终止翻译”的按钮
        self.primaryButton_terminate_translation = PushButton('取消翻译', self, FluentIcon.CANCEL)
        self.primaryButton_terminate_translation.clicked.connect(self.terminate_translation) #按钮绑定槽函数


        layout_start_translation.addStretch(1)  # 添加伸缩项
        layout_start_translation.addWidget(self.primaryButton_start_translation)
        layout_start_translation.addWidget(self.primaryButton_continue_translation)
        layout_start_translation.addWidget(self.primaryButton_pause_translation)
        layout_start_translation.addStretch(1)  # 添加伸缩项
        layout_start_translation.addWidget(self.primaryButton_terminate_translation)
        layout_start_translation.addStretch(1)  # 添加伸缩项
        box_start_translation.setLayout(layout_start_translation)



        self.container.addWidget(self.card_layout)
        self.container.addWidget(box_start_translation)


    #开始翻译按钮绑定函数
    def Start_translation(self):

        # 判断是否可以开始翻译
        if self.background_executor.Start_translation_switch(self):
            #隐藏开始翻译按钮
            self.primaryButton_start_translation.hide()
            #显示暂停翻译按钮
            self.primaryButton_pause_translation.show()

            #创建子线程
            thread = self.background_executor("开始翻译","","","","","","","")
            thread.start()


    
    # 暂停翻译按钮绑定函数
    def pause_translation(self):

        # 隐藏暂停翻译按钮
        self.primaryButton_pause_translation.hide()
        # 显示继续翻译按钮
        self.primaryButton_continue_translation.show()

        # 暂停翻译实现函数
        self.background_executor.Pause_translation(self)


    #继续翻译按钮绑定函数
    def continue_translation(self):
        
        # 如果已经暂停完成
        if self.background_executor.Continue_translation_switch(self):
            # 隐藏继续翻译按钮
            self.primaryButton_continue_translation.hide()
            # 显示暂停翻译按钮
            self.primaryButton_pause_translation.show()

            # 创建子线程
            thread = self.background_executor("开始翻译","","","","","","","")
            thread.start()

    
    #取消翻译按钮绑定函数
    def terminate_translation(self):

        # 隐藏继续翻译按钮
        self.primaryButton_continue_translation.hide()
        # 隐藏暂停翻译按钮
        self.primaryButton_pause_translation.hide()
        # 显示开始翻译按钮
        self.primaryButton_start_translation.show()

       # 取消翻译实现函数
        self.background_executor.Cancel_translation(self)
