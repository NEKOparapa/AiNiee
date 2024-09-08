
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar


class Widget_translation_settings_B3(QFrame):#  专项设置子界面
    def __init__(self, text: str, parent=None,user_interface_prompter=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.user_interface_prompter = user_interface_prompter
        #设置各个控件-----------------------------------------------------------------------------------------


        # ----------
        check1_box = QGroupBox()
        check1_box.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        check1_layout = QHBoxLayout()

        #设置标签
        labe1_6 = QLabel(flags=Qt.WindowFlags())  
        labe1_6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_6.setText("模型退化检查")

       #设置选择开关
        self.SwitchButton_check1 = SwitchButton(parent=self)    
        self.SwitchButton_check1.setChecked(True)


        check1_layout.addWidget(labe1_6)
        check1_layout.addStretch(1)  # 添加伸缩项
        check1_layout.addWidget(self.SwitchButton_check1)
        check1_box.setLayout(check1_layout)


        # ----------
        check2_box = QGroupBox()
        check2_box.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        check2_layout = QHBoxLayout()

        #设置标签
        labe1_6 = QLabel(flags=Qt.WindowFlags())  
        labe1_6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_6.setText("残留部分原文检查")

        # 设置开关
        self.SwitchButton_check2 = SwitchButton(parent=self)    
        self.SwitchButton_check2.setChecked(True)


        check2_layout.addWidget(labe1_6)
        check2_layout.addStretch(1)  # 添加伸缩项
        check2_layout.addWidget(self.SwitchButton_check2)
        check2_box.setLayout(check2_layout)


        # ----------
        check3_box = QGroupBox()
        check3_box.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        check3_layout = QHBoxLayout()

        # 设置标签
        labe1_4 = QLabel(flags=Qt.WindowFlags())  
        labe1_4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_4.setText("返回相同原文检查")



        # 设置选择开关
        self.SwitchButton_check3 = SwitchButton(parent=self)    
        self.SwitchButton_check3.setChecked(True)



        check3_layout.addWidget(labe1_4)
        check3_layout.addStretch(1)  # 添加伸缩项
        check3_layout.addWidget(self.SwitchButton_check3)
        check3_box.setLayout(check3_layout)




        # 最外层的垂直布局
        container = QVBoxLayout()

        # 把内容添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(check1_box)
        container.addWidget(check2_box)
        container.addWidget(check3_box)
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下


