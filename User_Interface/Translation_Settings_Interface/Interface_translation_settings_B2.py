
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar


class Widget_translation_settings_B2(QFrame):#  专项设置子界面
    def __init__(self, text: str, parent=None,user_interface_prompter=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.user_interface_prompter = user_interface_prompter
        #设置各个控件-----------------------------------------------------------------------------------------


        # -----创建第3个组(后来补的)，添加多个组件-----
        box1_cot_toggle = QGroupBox()
        box1_cot_toggle.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1_cot_toggle = QHBoxLayout()

        #设置“简繁转换开关”标签
        labe1_6 = QLabel(flags=Qt.WindowFlags())  
        labe1_6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_6.setText("使用思维链翻译")

       #设置“简繁体自动转换”选择开关
        self.SwitchButton_cot_toggle = SwitchButton(parent=self)    



        layout1_cot_toggle.addWidget(labe1_6)
        layout1_cot_toggle.addStretch(1)  # 添加伸缩项
        layout1_cot_toggle.addWidget(self.SwitchButton_cot_toggle)
        box1_cot_toggle.setLayout(layout1_cot_toggle)


        # -----创建第3个组(后来补的)，添加多个组件-----
        box1_cn_prompt_toggle = QGroupBox()
        box1_cn_prompt_toggle.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1_cn_prompt_toggle = QHBoxLayout()

        #设置“简繁转换开关”标签
        labe1_6 = QLabel(flags=Qt.WindowFlags())  
        labe1_6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_6.setText("使用中文提示词")

       #设置“简繁体自动转换”选择开关
        self.SwitchButton_cn_prompt_toggle = SwitchButton(parent=self)    



        layout1_cn_prompt_toggle.addWidget(labe1_6)
        layout1_cn_prompt_toggle.addStretch(1)  # 添加伸缩项
        layout1_cn_prompt_toggle.addWidget(self.SwitchButton_cn_prompt_toggle)
        box1_cn_prompt_toggle.setLayout(layout1_cn_prompt_toggle)


        # -----创建第1个组(后来补的)，添加多个组件-----
        box_clear = QGroupBox()
        box_clear.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_clear = QHBoxLayout()

        #设置标签
        labe1_4 = QLabel(flags=Qt.WindowFlags())  
        labe1_4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_4.setText("处理首尾非文本字符")



       #设置选择开关
        self.SwitchButton_clear = SwitchButton(parent=self)    
        self.SwitchButton_clear.checkedChanged.connect(self.on_clear)



        layout_clear.addWidget(labe1_4)
        layout_clear.addStretch(1)  # 添加伸缩项
        layout_clear.addWidget(self.SwitchButton_clear)
        box_clear.setLayout(layout_clear)



        # -----创建第3个组(后来补的)，添加多个组件-----
        box1_conversion_toggle = QGroupBox()
        box1_conversion_toggle.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1_conversion_toggle = QHBoxLayout()

        #设置“简繁转换开关”标签
        labe1_6 = QLabel(flags=Qt.WindowFlags())  
        labe1_6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_6.setText("中文字体转换")

       #设置“简繁体自动转换”选择开关
        self.SwitchButton_conversion_toggle = SwitchButton(parent=self)    



        layout1_conversion_toggle.addWidget(labe1_6)
        layout1_conversion_toggle.addStretch(1)  # 添加伸缩项
        layout1_conversion_toggle.addWidget(self.SwitchButton_conversion_toggle)
        box1_conversion_toggle.setLayout(layout1_conversion_toggle)



        # -----创建第4个组(后来补的)，添加多个组件-----
        box_opencc_preset = QGroupBox()
        box_opencc_preset.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")  # 分别设置了边框大小，边框颜色，边框圆角
        layout_opencc_preset = QHBoxLayout()


        #设置“OpenCC 配置”标签
        labe1_7 = QLabel(parent=self, flags=Qt.WindowFlags())  
        labe1_7.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        labe1_7.setText("字体转换配置")

        #设置“OpenCC 配置”下拉选择框
        self.comboBox_opencc_preset = ComboBox()  # 以demo为父类
        self.comboBox_opencc_preset.addItems(['s2t', 't2s', 's2tw', 'tw2s', 's2hk', 'hk2s', 's2twp', 'tw2sp', 't2tw', 'hk2t', 't2hk', 't2jp', 'jp2t', 'tw2t'])
        self.comboBox_opencc_preset.setCurrentIndex(0)  # 设置下拉框控件（ComboBox）的当前选中项的索引为 0，也就是默认选中第一个选项
        self.comboBox_opencc_preset.setFixedSize(127, 30)


        layout_opencc_preset.addWidget(labe1_7)
        layout_opencc_preset.addWidget(self.comboBox_opencc_preset)
        box_opencc_preset.setLayout(layout_opencc_preset)



        # -----创建第5个组(后来补的)，添加多个组件-----
        box1_line_breaks = QGroupBox()
        box1_line_breaks.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1_line_breaks = QHBoxLayout()

        #设置“换行符保留”标签
        labe1_6 = QLabel(flags=Qt.WindowFlags())  
        labe1_6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_6.setText("换行替换后翻译")

       #设置“换行符保留”选择开关
        self.SwitchButton_line_breaks = SwitchButton(parent=self)    



        layout1_line_breaks.addWidget(labe1_6)
        layout1_line_breaks.addStretch(1)  # 添加伸缩项
        layout1_line_breaks.addWidget(self.SwitchButton_line_breaks)
        box1_line_breaks.setLayout(layout1_line_breaks)




        # 最外层的垂直布局
        container = QVBoxLayout()

        # 把内容添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box1_cot_toggle)
        container.addWidget(box1_cn_prompt_toggle)
        container.addWidget(box1_line_breaks)
        container.addWidget(box_clear)
        container.addWidget(box1_conversion_toggle)
        container.addWidget(box_opencc_preset)
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下


    #设置选择开关绑定函数
    def on_clear(self, isChecked: bool):
        if isChecked:
            self.user_interface_prompter.createWarningInfoBar("仅支持翻译日语文本时生效，建议翻译T++导出文件时开启")
