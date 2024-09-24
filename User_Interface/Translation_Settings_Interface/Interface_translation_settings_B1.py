
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar




class Widget_translation_settings_B1(QFrame):#  发送设置子界面
    def __init__(self, text: str, parent=None,user_interface_prompter=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.user_interface_prompter = user_interface_prompter
        #设置各个控件-----------------------------------------------------------------------------------------


        # -----创建第个组，添加多个组件-----
        box_lines_limit = QGroupBox()
        box_lines_limit.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_lines_limit = QHBoxLayout()

        #设置标签
        label4 = QLabel(flags=Qt.WindowFlags())  
        label4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        label4.setText("每次翻译")

        self.spinBox_lines_limit = SpinBox(self)
        self.spinBox_lines_limit.setRange(0, 99999)    
        self.spinBox_lines_limit.setValue(15)

        #设置“说明”显示
        self.labelA_lines = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.labelA_lines.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 15px")
        self.labelA_lines.setText("(行)")  


        # 设置开关
        self.checkBox_lines_limit_switch = CheckBox('使用行数模式', self)
        self.checkBox_lines_limit_switch.setChecked(True)
        self.checkBox_lines_limit_switch.stateChanged.connect(self.on_lines)

        layout_lines_limit.addWidget(label4)
        layout_lines_limit.addWidget(self.spinBox_lines_limit)
        layout_lines_limit.addWidget( self.labelA_lines)
        layout_lines_limit.addStretch(1)
        layout_lines_limit.addWidget(self.checkBox_lines_limit_switch)
        box_lines_limit.setLayout(layout_lines_limit)


        # -----创建第个组，添加多个组件-----
        box_tokens_limit = QGroupBox()
        box_tokens_limit.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_tokens_limit = QHBoxLayout()

        #设置标签
        label4 = QLabel(flags=Qt.WindowFlags())  
        label4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        label4.setText("每次翻译")

        self.spinBox_tokens_limit = SpinBox(self)
        self.spinBox_tokens_limit.setRange(0, 99999)    
        self.spinBox_tokens_limit.setValue(1500)

        #设置“说明”显示
        self.labelA_tokens = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.labelA_tokens.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 15px")
        self.labelA_tokens.setText("(tokens)")  


        # 设置开关
        self.checkBox_tokens_limit_switch = CheckBox('使用tokens模式', self)
        self.checkBox_tokens_limit_switch.setChecked(False)
        self.checkBox_tokens_limit_switch.stateChanged.connect(self.on_tokens)

        layout_tokens_limit.addWidget(label4)
        layout_tokens_limit.addWidget(self.spinBox_tokens_limit)
        layout_tokens_limit.addWidget( self.labelA_tokens)
        layout_tokens_limit.addStretch(1)
        layout_tokens_limit.addWidget(self.checkBox_tokens_limit_switch)
        box_tokens_limit.setLayout(layout_tokens_limit)



        # -----创建第1个组，添加多个组件-----
        box_pre_lines = QGroupBox()
        box_pre_lines.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_pre_lines = QHBoxLayout()

        #设置标签
        label1 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label1.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        label1.setText("携带上文行数")


        #设置数值输入框
        self.spinBox_pre_lines = SpinBox(self)
        self.spinBox_pre_lines.setRange(0, 1000)    
        self.spinBox_pre_lines.setValue(0)


        layout_pre_lines.addWidget(label1)
        layout_pre_lines.addStretch(1)  # 添加伸缩项
        layout_pre_lines.addWidget(self.spinBox_pre_lines)
        box_pre_lines.setLayout(layout_pre_lines)



        # -----创建第1个组(后来补的)，添加多个组件-----
        box1_thread_count = QGroupBox()
        box1_thread_count.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1_thread_count = QHBoxLayout()

        #设置“最大线程数”标签
        label1_7 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label1_7.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        label1_7.setText("最大线程数")

        #设置“说明”显示
        label2_7 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label2_7.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px")
        label2_7.setText("(0是自动根据电脑设置线程数)")  

       #设置“最大线程数”数值输入框
        self.spinBox_thread_count = SpinBox(self)
        #设置最大最小值
        self.spinBox_thread_count.setRange(0, 1000)    
        self.spinBox_thread_count.setValue(0)

        layout1_thread_count.addWidget(label1_7)
        layout1_thread_count.addWidget(label2_7)
        layout1_thread_count.addStretch(1)  # 添加伸缩项
        layout1_thread_count.addWidget(self.spinBox_thread_count)
        box1_thread_count.setLayout(layout1_thread_count)


        # -----创建第x个组，添加多个组件-----
        box_retry_count_limit = QGroupBox()
        box_retry_count_limit.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_retry_count_limit = QHBoxLayout()


        label1_7 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label1_7.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        label1_7.setText("错误重翻最大次数限制")


        # 设置数值输入框
        self.spinBox_retry_count_limit = SpinBox(self)
        # 设置最大最小值
        self.spinBox_retry_count_limit.setRange(0, 1000)    
        self.spinBox_retry_count_limit.setValue(1)

        layout_retry_count_limit.addWidget(label1_7)
        layout_retry_count_limit.addStretch(1)  # 添加伸缩项
        layout_retry_count_limit.addWidget(self.spinBox_retry_count_limit)
        box_retry_count_limit.setLayout(layout_retry_count_limit)


        # -----创建第x个组，添加多个组件-----
        box_round_limit = QGroupBox()
        box_round_limit.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_round_limit = QHBoxLayout()


        label1_7 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label1_7.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        label1_7.setText("翻译流程最大轮次限制")


        # 设置数值输入框
        self.spinBox_round_limit = SpinBox(self)
        # 设置最大最小值
        self.spinBox_round_limit.setRange(3, 1000)    
        self.spinBox_round_limit.setValue(6)

        layout_round_limit.addWidget(label1_7)
        layout_round_limit.addStretch(1)  # 添加伸缩项
        layout_round_limit.addWidget(self.spinBox_round_limit)
        box_round_limit.setLayout(layout_round_limit)


        # 最外层的垂直布局
        container = QVBoxLayout()

        # 把内容添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box_lines_limit)
        container.addWidget(box_tokens_limit)
        container.addWidget(box_pre_lines)
        container.addWidget(box1_thread_count)
        container.addWidget(box_retry_count_limit)
        container.addWidget(box_round_limit)
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下


    #设置选择开关绑定函数
    def on_clear(self, isChecked: bool):
        if isChecked:
            self.user_interface_prompter.createWarningInfoBar("仅支持翻译日语文本时生效，建议翻译T++导出文件时开启")

    #设互斥开关函数
    def on_lines(self, isChecked: bool):
        if isChecked:
            self.checkBox_tokens_limit_switch.setChecked(False)

    #设互斥开关函数
    def on_tokens(self, isChecked: bool):
        if isChecked:
            self.checkBox_lines_limit_switch.setChecked(False)
