
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar



class Widget_translation_settings_C(QFrame):#  混合翻译设置子界面
    def __init__(self, text: str, parent=None,user_interface_prompter=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.user_interface_prompter = user_interface_prompter
        #设置各个控件-----------------------------------------------------------------------------------------



        # -----创建第1个组，添加多个组件-----
        box_switch = QGroupBox()
        box_switch.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_switch = QHBoxLayout()

        #设置标签
        self.labe1_4 = QLabel(flags=Qt.WindowFlags())  
        self.labe1_4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        self.labe1_4.setText("启用混合平台翻译功能")



        # 设置选择开关
        self.SwitchButton_mixed_translation = SwitchButton(parent=self)    
        self.SwitchButton_mixed_translation.checkedChanged.connect(self.test)



        layout_switch.addWidget(self.labe1_4)
        layout_switch.addStretch(1)  # 添加伸缩项
        layout_switch.addWidget(self.SwitchButton_mixed_translation)
        box_switch.setLayout(layout_switch)





        # -----创建第2个组，添加多个组件-----
        box_translation_platform1 = QGroupBox()
        box_translation_platform1.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_translation_platform1 = QGridLayout()

        #设置“翻译平台”标签
        self.labelx1 = QLabel( flags=Qt.WindowFlags())  
        self.labelx1.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")#设置字体，大小，颜色
        self.labelx1.setText("首轮翻译平台")


        #设置“翻译平台”下拉选择框
        self.comboBox_primary_translation_platform = ComboBox() #以demo为父类
        self.comboBox_primary_translation_platform.addItems(['OpenAI官方',  'Google官方', 'Anthropic官方',  'Cohere官方',  'Moonshot官方',  'Deepseek官方',  'Dashscope官方', 'Volcengine官方', '零一万物官方',  '智谱官方',  '代理平台',  'SakuraLLM'])
        self.comboBox_primary_translation_platform.setCurrentIndex(0) #设置下拉框控件（ComboBox）的当前选中项的索引为0，也就是默认选中第一个选项
        self.comboBox_primary_translation_platform.setFixedSize(150, 35)


        layout_translation_platform1.addWidget(self.labelx1, 0, 0)
        layout_translation_platform1.addWidget(self.comboBox_primary_translation_platform, 0, 1)
        box_translation_platform1.setLayout(layout_translation_platform1)



        # -----创建第3个组，添加多个组件-----
        box_translation_platform2 = QGroupBox()
        box_translation_platform2.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_translation_platform2 = QGridLayout()

        #设置“翻译平台”标签
        self.labelx2 = QLabel( flags=Qt.WindowFlags())  
        self.labelx2.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")#设置字体，大小，颜色
        self.labelx2.setText("次轮翻译平台")


        #设置“翻译平台”下拉选择框
        self.comboBox_secondary_translation_platform = ComboBox() #以demo为父类
        self.comboBox_secondary_translation_platform.addItems(['不设置', 'OpenAI官方',  'Google官方', 'Anthropic官方',  'Cohere官方',  'Moonshot官方',  'Deepseek官方',  'Dashscope官方', 'Volcengine官方', '零一万物官方',  '智谱官方',  '代理平台',  'SakuraLLM'])
        self.comboBox_secondary_translation_platform.setCurrentIndex(0) #设置下拉框控件（ComboBox）的当前选中项的索引为0，也就是默认选中第一个选项
        self.comboBox_secondary_translation_platform.setFixedSize(150, 35)


        layout_translation_platform2.addWidget(self.labelx2, 0, 0)
        layout_translation_platform2.addWidget(self.comboBox_secondary_translation_platform, 0, 1)
        box_translation_platform2.setLayout(layout_translation_platform2)



        # -----创建第4个组，添加多个组件-----
        box_translation_platform3 = QGroupBox()
        box_translation_platform3.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_translation_platform3 = QGridLayout()

        #设置“翻译平台”标签
        self.labelx3 = QLabel( flags=Qt.WindowFlags())  
        self.labelx3.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px; ")#设置字体，大小，颜色
        self.labelx3.setText("末轮翻译平台")


        #设置“翻译平台”下拉选择框
        self.comboBox_final_translation_platform = ComboBox() #以demo为父类
        self.comboBox_final_translation_platform.addItems(['不设置','OpenAI官方',  'Google官方', 'Anthropic官方',  'Cohere官方',  'Moonshot官方',  'Deepseek官方',  'Dashscope官方', 'Volcengine官方', '零一万物官方',  '智谱官方',  '代理平台',  'SakuraLLM'])
        self.comboBox_final_translation_platform.setCurrentIndex(0) #设置下拉框控件（ComboBox）的当前选中项的索引为0，也就是默认选中第一个选项
        self.comboBox_final_translation_platform.setFixedSize(150, 35)


        layout_translation_platform3.addWidget(self.labelx3, 0, 0)
        layout_translation_platform3.addWidget(self.comboBox_final_translation_platform, 0, 1)
        box_translation_platform3.setLayout(layout_translation_platform3)



        # -----创建第1个组，添加多个组件-----
        box_split_switch = QGroupBox()
        box_split_switch.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_split_switch = QHBoxLayout()

        #设置标签
        self.labe1_split_switch = QLabel(flags=Qt.WindowFlags())  
        self.labe1_split_switch.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        self.labe1_split_switch.setText("更换轮次后不进行文本拆分")



        # 设置选择开关
        self.SwitchButton_split_switch = SwitchButton(parent=self)    
        #self.SwitchButton_split_switch.checkedChanged.connect(self.test)



        layout_split_switch.addWidget(self.labe1_split_switch)
        layout_split_switch.addStretch(1)  # 添加伸缩项
        layout_split_switch.addWidget(self.SwitchButton_split_switch)
        box_split_switch.setLayout(layout_split_switch)



        # 最外层的垂直布局
        container = QVBoxLayout()

        # 把内容添加到容器中
        #container.addStretch(1)  # 添加伸缩项
        container.addWidget(box_switch)
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box_translation_platform1)
        container.addWidget(box_translation_platform2)
        container.addWidget(box_translation_platform3)
        container.addWidget( box_split_switch)
        container.addStretch(1)  # 添加伸缩项
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下


    #设置开关绑定函数
    def test(self, isChecked: bool):
        if isChecked:
            self.user_interface_prompter.createWarningInfoBar("请注意，开启该开关下面设置才会生效，并且会覆盖基础设置中的翻译平台")

