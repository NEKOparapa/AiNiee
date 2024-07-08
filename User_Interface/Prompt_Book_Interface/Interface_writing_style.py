from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar

class Widget_writing_style(QFrame): # 写作风格界面

    def __init__(self, text: str, parent=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用

        # -----创建第1个组，添加多个组件-----
        box1 = QGroupBox()
        box1.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1 = QHBoxLayout()


        label1 = QLabel( flags=Qt.WindowFlags())  
        label1.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")
        label1.setText("添加文风设定")


        self.label2 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label2.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px;  color: black")
        self.label2.setText("(全程加入)")


        self.checkBox1 = CheckBox('启用功能')
        #self.checkBox1.stateChanged.connect(self.checkBoxChanged1)

        layout1.addWidget(label1)
        layout1.addWidget(self.label2)
        layout1.addStretch(1)  # 添加伸缩项
        layout1.addWidget(self.checkBox1)
        box1.setLayout(layout1)


        # -----创建第2个组，添加多个组件-----
        box2 = QGroupBox()
        box2.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout2 = QHBoxLayout()


        Prompt = f'''None
'''


        self.TextEdit1 = TextEdit()
        #设置输入框最小高度
        self.TextEdit1.setMinimumHeight(180)
        #设置默认文本
        self.TextEdit1.setText(Prompt)


        layout2.addWidget(self.TextEdit1)
        box2.setLayout(layout2)



        # -----最外层容器设置垂直布局-----
        container = QVBoxLayout()

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(20) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下

        # 把各个组添加到容器中
        container.addWidget(box1)
        container.addWidget(box2)

