
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import StrongBodyLabel
from qframelesswindow import FramelessWindow, StandardTitleBar



class Widget_start_translation(QFrame):  # 开始翻译主界面
    def __init__(self, text: str, parent=None,configurator=None,user_interface_prompter=None,background_executor=None):  # 构造函数，初始化实例时会自动调用
        super().__init__(parent=parent)  # 调用父类 QWidget 的构造函数
        self.setObjectName(text.replace(' ', '-'))  # 设置对象名，用于在 NavigationInterface 中的 addItem 方法中的 routeKey 参数中使用
        self.configurator = configurator
        self.user_interface_prompter = user_interface_prompter
        self.background_executor = background_executor


        self.pivot = SegmentedWidget(self)  # 创建一个 SegmentedWidget 实例，分段式导航栏
        self.stackedWidget = QStackedWidget(self)  # 创建一个 QStackedWidget 实例，堆叠式窗口
        self.vBoxLayout = QVBoxLayout(self)  # 创建一个垂直布局管理器

        self.A_settings = Widget_start_translation_A('A_settings', self,configurator,user_interface_prompter,background_executor)  # 创建实例，指向界面
        self.B_settings = Widget_start_translation_B('B_settings', self,configurator,user_interface_prompter,background_executor)  # 创建实例，指向界面

        # 添加子界面到分段式导航栏
        self.addSubInterface(self.A_settings, 'A_settings', '开始翻译')
        self.addSubInterface(self.B_settings, 'B_settings', '备份功能')

        # 将分段式导航栏和堆叠式窗口添加到垂直布局中
        self.vBoxLayout.addWidget(self.pivot)
        self.vBoxLayout.addWidget(self.stackedWidget)
        self.vBoxLayout.setContentsMargins(30, 50, 30, 30)  # 设置布局的外边距

        # 连接堆叠式窗口的 currentChanged 信号到槽函数 onCurrentIndexChanged
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.A_settings)  # 设置默认显示的子界面为xxx界面
        self.pivot.setCurrentItem(self.A_settings.objectName())  # 设置分段式导航栏的当前项为xxx界面

    def addSubInterface(self, widget: QLabel, objectName, text):
        """
        添加子界面到堆叠式窗口和分段式导航栏
        """
        widget.setObjectName(objectName)
        #widget.setAlignment(Qt.AlignCenter) # 设置 widget 对象的文本（如果是文本控件）在控件中的水平对齐方式
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget),
        )

    def onCurrentIndexChanged(self, index):
        """
        槽函数：堆叠式窗口的 currentChanged 信号的槽函数
        """
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())


class Widget_start_translation_A(QFrame):#  开始翻译子界面
    def __init__(self, text: str, parent=None,configurator=None,user_interface_prompter=None,background_executor=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.configurator = configurator
        self.user_interface_prompter = user_interface_prompter
        self.background_executor = background_executor
        #设置各个控件-----------------------------------------------------------------------------------------


        # -----创建第1个组，添加多个组件-----
        box_project = QGroupBox()
        box_project.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")  # 分别设置了边框大小，边框颜色，边框圆角
        layout_project = QHBoxLayout()

        # 第一组水平布局
        layout_horizontal_1 = QHBoxLayout()

        self.label111 = StrongBodyLabel()
        # self.label111.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.label111.setText("项目类型 :")

        self.translation_project = StrongBodyLabel()
        # self.translation_project.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.translation_project.setText("无")

        layout_horizontal_1.addWidget(self.label111)
        layout_horizontal_1.addStretch(1)  # 添加伸缩项
        layout_horizontal_1.addWidget(self.translation_project)
        layout_horizontal_1.addStretch(1)  # 添加伸缩项

        # 第二组水平布局
        layout_horizontal_2 = QHBoxLayout()

        self.label222 = StrongBodyLabel()
        # self.label222.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.label222.setText("项目ID :")

        self.project_id = StrongBodyLabel()
        # self.project_id.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.project_id.setText("无")

        layout_horizontal_2.addWidget(self.label222)
        layout_horizontal_2.addStretch(1)  # 添加伸缩项
        layout_horizontal_2.addWidget(self.project_id)
        layout_horizontal_2.addStretch(1)  # 添加伸缩项

        # 将两个水平布局放入最外层水平布局
        layout_project.addLayout(layout_horizontal_1)
        layout_project.addLayout(layout_horizontal_2)

        box_project.setLayout(layout_project)


        # -----创建第2个组，添加多个组件-----
        box_text_line_count = QGroupBox()
        box_text_line_count.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")  # 分别设置了边框大小，边框颜色，边框圆角
        layout_text_line_count = QHBoxLayout()

        # 第三组水平布局
        layout_horizontal_3 = QHBoxLayout()

        self.label333 = StrongBodyLabel()
        # self.label333.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.label333.setText("总文本行数 :")

        self.total_text_line_count = StrongBodyLabel()
        # self.total_text_line_count.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.total_text_line_count.setText("无")

        layout_horizontal_3.addWidget(self.label333)
        layout_horizontal_3.addStretch(1)  # 添加伸缩项
        layout_horizontal_3.addWidget(self.total_text_line_count)
        layout_horizontal_3.addStretch(1)  # 添加伸缩项

        # 第四组水平布局
        layout_horizontal_4 = QHBoxLayout()

        self.label444 = StrongBodyLabel()
        # self.label444.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.label444.setText("已翻译行数 :")

        self.translated_line_count = StrongBodyLabel()
        # self.translated_line_count.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.translated_line_count.setText("无")

        layout_horizontal_4.addWidget(self.label444)
        layout_horizontal_4.addStretch(1)  # 添加伸缩项
        layout_horizontal_4.addWidget(self.translated_line_count)
        layout_horizontal_4.addStretch(1)  # 添加伸缩项

        # 将第三组和第四组水平布局放入最外层水平布局
        layout_text_line_count.addLayout(layout_horizontal_3)
        layout_text_line_count.addLayout(layout_horizontal_4)

        box_text_line_count.setLayout(layout_text_line_count)





        # -----创建第3个组，添加多个组件-----
        box_spent = QGroupBox()
        box_spent.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")  # 分别设置了边框大小，边框颜色，边框圆角
        layout_spent = QHBoxLayout()

        # 第五组水平布局
        layout_horizontal_5 = QHBoxLayout()

        self.labelx1 = StrongBodyLabel()
        # self.labelx1.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.labelx1.setText("已花费tokens :")

        self.tokens_spent = StrongBodyLabel()
        # self.tokens_spent.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.tokens_spent.setText("无")

        layout_horizontal_5.addWidget(self.labelx1)
        layout_horizontal_5.addStretch(1)  # 添加伸缩项
        layout_horizontal_5.addWidget(self.tokens_spent)
        layout_horizontal_5.addStretch(1)  # 添加伸缩项

        # 第六组水平布局
        layout_horizontal_6 = QHBoxLayout()

        self.labelx2 = StrongBodyLabel()
        # self.labelx2.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.labelx2.setText("已花费金额(＄) :")

        self.amount_spent = StrongBodyLabel()
        # self.amount_spent.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.amount_spent.setText("无")

        layout_horizontal_6.addWidget(self.labelx2)
        layout_horizontal_6.addStretch(1)  # 添加伸缩项
        layout_horizontal_6.addWidget(self.amount_spent)
        layout_horizontal_6.addStretch(1)  # 添加伸缩项

        # 将第五组和第六组水平布局放入最外层水平布局
        layout_spent.addLayout(layout_horizontal_5)
        layout_spent.addLayout(layout_horizontal_6)

        box_spent.setLayout(layout_spent)


        # -----创建第4个组，添加多个组件-----
        box_status = QGroupBox()
        box_status.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")  # 分别设置了边框大小，边框颜色，边框圆角
        layout_status = QHBoxLayout()

        # 第7组水平布局
        layout_horizontal_7 = QHBoxLayout()

        self.labelx111 = StrongBodyLabel()
        # self.labelx111.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.labelx111.setText("运行状态 :")

        self.running_status = StrongBodyLabel()
        # self.running_status.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.running_status.setText("无")

        layout_horizontal_7.addWidget(self.labelx111)
        layout_horizontal_7.addStretch(1)  # 添加伸缩项
        layout_horizontal_7.addWidget(self.running_status)
        layout_horizontal_7.addStretch(1)  # 添加伸缩项

        # 第8组水平布局
        layout_horizontal_8 = QHBoxLayout()

        self.labelx222 = StrongBodyLabel()
        # self.labelx222.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.labelx222.setText("运行线程数 :")

        self.thread_count = StrongBodyLabel()
        # self.thread_count.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.thread_count.setText("无")

        layout_horizontal_8.addWidget(self.labelx222)
        layout_horizontal_8.addStretch(1)  # 添加伸缩项
        layout_horizontal_8.addWidget(self.thread_count)
        layout_horizontal_8.addStretch(1)  # 添加伸缩项

        # 将第7组和第8组水平布局放入最外层水平布局
        layout_status.addLayout(layout_horizontal_7)
        layout_status.addLayout(layout_horizontal_8)

        box_status.setLayout(layout_status)


        # -----创建第9个组，添加多个组件-----
        box_translation_speed = QGroupBox()
        box_translation_speed.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")  # 分别设置了边框大小，边框颜色，边框圆角
        layout_translation_speed = QHBoxLayout()

        # 第9组水平布局
        layout_horizontal_9 = QHBoxLayout()

        self.label9 = StrongBodyLabel()
        # self.label9.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.label9.setText("翻译速度(token/s) :")

        self.translation_speed_token = StrongBodyLabel()
        # self.translation_speed_token.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.translation_speed_token.setText("无")

        layout_horizontal_9.addWidget(self.label9)
        layout_horizontal_9.addStretch(1)  # 添加伸缩项
        layout_horizontal_9.addWidget(self.translation_speed_token)
        layout_horizontal_9.addStretch(1)  # 添加伸缩项

        # 第10组水平布局
        layout_horizontal_10 = QHBoxLayout()

        self.label10 = StrongBodyLabel()
        # self.label10.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.label10.setText("翻译速度(line/s) :")

        self.translation_speed_line = StrongBodyLabel()
        # self.translation_speed_line.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")  # 设置字体，大小，颜色
        self.translation_speed_line.setText("无")

        layout_horizontal_10.addWidget(self.label10)
        layout_horizontal_10.addStretch(1)  # 添加伸缩项
        layout_horizontal_10.addWidget(self.translation_speed_line)
        layout_horizontal_10.addStretch(1)  # 添加伸缩项

        # 将第九组和第十组水平布局放入最外层水平布局
        layout_translation_speed.addLayout(layout_horizontal_9)
        layout_translation_speed.addLayout(layout_horizontal_10)

        box_translation_speed.setLayout(layout_translation_speed)


        # -----创建第5个组，添加多个组件-----
        box_progressRing = QGroupBox()
        box_progressRing.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_progressRing = QHBoxLayout()


        #设置“翻译进度”标签
        self.label_progressRing = StrongBodyLabel()
        # self.label_progressRing.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")#设置字体，大小，颜色
        self.label_progressRing.setText("翻译进度")

        #设置翻译进度条
        self.progressRing = ProgressRing(self)
        self.progressRing.setValue(0)
        self.progressRing.setTextVisible(True)
        self.progressRing.setFixedSize(80, 80)


        layout_progressRing.addWidget(self.label_progressRing)
        layout_progressRing.addStretch(1)  # 添加伸缩项
        layout_progressRing.addWidget(self.progressRing)
        box_progressRing.setLayout(layout_progressRing)





        # -----创建第6个组，添加多个组件-----
        box_start_translation = QGroupBox()
        box_start_translation.setStyleSheet(""" QGroupBox {border: 0px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_start_translation = QHBoxLayout()


        #设置“开始翻译”的按钮
        self.primaryButton_start_translation = PrimaryPushButton('开始翻译', self, FIF.PLAY)
        self.primaryButton_start_translation.clicked.connect(self.Start_translation) #按钮绑定槽函数


        #设置“暂停翻译”的按钮
        self.primaryButton_pause_translation = PrimaryPushButton('暂停翻译', self, FIF.PAUSE)
        self.primaryButton_pause_translation.clicked.connect(self.pause_translation) #按钮绑定槽函数
        #隐藏按钮
        self.primaryButton_pause_translation.hide()

        #设置“继续翻译”的按钮
        self.primaryButton_continue_translation = PrimaryPushButton('继续翻译', self, FIF.ROTATE)
        self.primaryButton_continue_translation.clicked.connect(self.continue_translation) #按钮绑定槽函数
        #隐藏按钮
        self.primaryButton_continue_translation.hide()


        #设置“终止翻译”的按钮
        self.primaryButton_terminate_translation = PushButton('取消翻译', self, FIF.CANCEL)
        self.primaryButton_terminate_translation.clicked.connect(self.terminate_translation) #按钮绑定槽函数




        layout_start_translation.addStretch(1)  # 添加伸缩项
        layout_start_translation.addWidget(self.primaryButton_start_translation)
        layout_start_translation.addWidget(self.primaryButton_continue_translation)
        layout_start_translation.addWidget(self.primaryButton_pause_translation)
        layout_start_translation.addStretch(1)  # 添加伸缩项
        layout_start_translation.addWidget(self.primaryButton_terminate_translation)
        layout_start_translation.addStretch(1)  # 添加伸缩项
        box_start_translation.setLayout(layout_start_translation)


        # 最外层的垂直布局
        container = QVBoxLayout()

        # 把内容添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box_project)
        container.addWidget(box_status)
        container.addWidget(box_text_line_count)
        container.addWidget(box_spent)
        container.addWidget(box_translation_speed)
        container.addWidget(box_progressRing)
        container.addWidget(box_start_translation)
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(20, 10, 20, 20) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下



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


class Widget_start_translation_B(QFrame):#  开始翻译子界面
    def __init__(self, text: str, parent=None,configurator=None,user_interface_prompter=None,background_executor=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.configurator = configurator
        self.user_interface_prompter = user_interface_prompter
        self.background_executor = background_executor
        #设置各个控件-----------------------------------------------------------------------------------------



        # -----创建第1个组，添加多个组件-----
        box_switch = QGroupBox()
        box_switch.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_switch = QHBoxLayout()


        label1 = StrongBodyLabel()
        # label1.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")
        label1.setText("自动备份缓存文件到输出文件夹")


        self.checkBox_switch = CheckBox('启用功能')
        self.checkBox_switch.setChecked(True)
        self.checkBox_switch.stateChanged.connect(self.checkBoxChanged1)

        layout_switch.addWidget(label1)
        layout_switch.addStretch(1)  # 添加伸缩项
        layout_switch.addWidget(self.checkBox_switch)
        box_switch.setLayout(layout_switch)



        # -----创建第1个组，添加多个组件-----
        box_export_cache_file_path = QGroupBox()
        box_export_cache_file_path.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_export_cache_file_path = QHBoxLayout()

        #设置“导出当前任务的缓存文件”标签
        label4 = StrongBodyLabel()  
        # label4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        label4.setText("导出当前任务的缓存文件")


        #设置导出当前任务的缓存文件按钮
        self.pushButton_export_cache_file_path = PushButton('选择文件夹', self, FIF.FOLDER)
        self.pushButton_export_cache_file_path.clicked.connect(self.output_cachedata) #按钮绑定槽函数



        layout_export_cache_file_path.addWidget(label4)
        layout_export_cache_file_path.addStretch(1)  # 添加伸缩项
        layout_export_cache_file_path.addWidget(self.pushButton_export_cache_file_path)
        box_export_cache_file_path.setLayout(layout_export_cache_file_path)


        # -----创建第2个组，添加多个组件-----
        box_export_translated_file_path = QGroupBox()
        box_export_translated_file_path.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_export_translated_file_path = QHBoxLayout()

        #设置“导出当前任务的已翻译文本”标签
        label6 = StrongBodyLabel() 
        # label6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        label6.setText("导出当前任务的已翻译文本")


        #设置导出当前任务的已翻译文本按钮
        self.pushButton_export_translated_file_path = PushButton('选择文件夹', self, FIF.FOLDER)
        self.pushButton_export_translated_file_path.clicked.connect(self.output_data) #按钮绑定槽函数


        

        layout_export_translated_file_path.addWidget(label6)
        layout_export_translated_file_path.addStretch(1)  # 添加伸缩项
        layout_export_translated_file_path.addWidget(self.pushButton_export_translated_file_path)
        box_export_translated_file_path.setLayout(layout_export_translated_file_path)







        # -----最外层容器设置垂直布局-----
        container = QVBoxLayout()

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(20, 10, 20, 20) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下

        # 把各个组添加到容器中
        container.addStretch(1)  # 添加伸缩项        
        container.addWidget(box_switch)
        container.addWidget(box_export_cache_file_path)
        container.addWidget(box_export_translated_file_path)
        container.addStretch(1)  # 添加伸缩项

    #提示函数
    def checkBoxChanged1(self, isChecked: bool):
        if isChecked :
            self.user_interface_prompter.createSuccessInfoBar("已开启自动备份功能")

    # 缓存文件输出
    def output_cachedata(self):

        label_output_path = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if label_output_path:
            print('[INFO] 已选择输出文件夹:' ,label_output_path)

            if len(self.configurator.cache_list)>= 3:
                #创建子线程
                thread = self.background_executor("输出缓存文件","",label_output_path,"","","","","")
                thread.start()
            else:
                print('[INFO] 未存在缓存文件')
                return  # 直接返回，不执行后续操作
        else :
            print('[INFO] 未选择文件夹')
            return  # 直接返回，不执行后续操作


    # 缓存文件输出
    def output_data(self):

        label_output_path = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if label_output_path:
            print('[INFO] 已选择输出文件夹:' ,label_output_path)

            if len(self.configurator.cache_list)>= 3:
                #创建子线程
                thread = self.background_executor("输出已翻译文件",self.configurator.label_input_path,label_output_path,"","","","","")
                thread.start()

            else:
                print('[INFO] 未存在缓存文件')
                return  # 直接返回，不执行后续操作
        else :
            print('[INFO] 未选择文件夹')
            return  # 直接返回，不执行后续操作

