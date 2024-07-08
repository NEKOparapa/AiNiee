
import os
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar

class Widget_sponsor(QFrame):# 赞助界面
    def __init__(self, text: str, parent=None,configurator=None):
        super().__init__(parent=parent)
        self.setObjectName(text.replace(' ', '-'))
        self.configurator = configurator
        # -----创建第1个组，添加多个组件-----
        box1 = QGroupBox()
        box1.setStyleSheet(""" QGroupBox {border: 0px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1 = QHBoxLayout()


        # 创建 QLabel 用于显示图片
        self.image_label = QLabel(self)
        # 通过 QPixmap 加载图片
        pixmap = QPixmap(os.path.join(self.configurator.resource_dir,"sponsor","赞赏码.png"))
        # 设置 QLabel 的固定大小
        self.image_label.setFixedSize(350, 350)
        # 调整 QLabel 大小以适应图片
        self.image_label.setPixmap(pixmap)
        self.image_label.setScaledContents(True)


        layout1.addWidget(self.image_label)
        box1.setLayout(layout1)
        


        # -----创建第2个组，添加多个组件-----
        box2 = QGroupBox()
        box2.setStyleSheet(""" QGroupBox {border: 0px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout2 = QHBoxLayout()


        # 创建 QLabel 用于显示文字
        self.text_label = QLabel(self)
        self.text_label.setStyleSheet("font-family: 'SimSun'; font-size: 19px;")
        #self.text_label.setText("个人开发不易，如果这个项目帮助到了您，可以考虑请作者喝一杯奶茶。您的支持就是作者开发和维护项目的动力！🙌")
        self.text_label.setText("喜欢我的项目吗？如果这个项目帮助到了您，赞助一杯奶茶，让我能更有动力更新哦！💖")

        layout2.addStretch(1)  # 添加伸缩项
        layout2.addWidget(self.text_label)
        layout2.addStretch(1)  # 添加伸缩项
        box2.setLayout(layout2)



        
        # -----最外层容器设置垂直布局-----
        container = QVBoxLayout()

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下

        # 把各个组添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box1)
        container.addWidget(box2)
        container.addStretch(1)  # 添加伸缩项