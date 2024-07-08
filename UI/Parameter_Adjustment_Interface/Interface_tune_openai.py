from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar


class Widget_tune_openai(QFrame):# oepnai调教界面
    def __init__(self, text: str, parent=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用


        # 最外层的垂直布局
        container = QVBoxLayout()


        # -----创建第1个组，添加多个组件-----
        box1 = QGroupBox()
        box1.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1 = QHBoxLayout()


        #设置“启用实时参数”标签
        label0 = QLabel(flags=Qt.WindowFlags())  
        label0.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        label0.setText("实时改变AI参数")

        #设置官方文档说明链接按钮
        hyperlinkButton = HyperlinkButton(
            url='https://platform.openai.com/docs/api-reference/chat/create',
            text='(官方文档)'
        )

        #设置“启用实时参数”开关
        self.checkBox = CheckBox('启用', self)
        #self.checkBox.stateChanged.connect(self.checkBoxChanged)


        layout1.addWidget(label0)
        layout1.addWidget(hyperlinkButton)
        layout1.addStretch(1)  # 添加伸缩项
        layout1.addWidget(self.checkBox)
        box1.setLayout(layout1)




        # -----创建第3个组，添加多个组件-----
        box3 = QGroupBox()
        box3.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout3 = QHBoxLayout()

        #设置“温度”标签
        label1 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label1.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        label1.setText("Temperature")

        #设置“温度”副标签
        label11 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label11.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 10px;  color: black")
        label11.setText("(官方默认值为1)")

        #设置“温度”滑动条
        self.slider1 = Slider(Qt.Horizontal, self)
        self.slider1.setFixedWidth(200)

        # 创建一个QLabel控件，并设置初始文本为滑动条的初始值,并实时更新
        self.label2 = QLabel(str(self.slider1.value()), self)
        self.label2.setFixedSize(100, 15)  # 设置标签框的大小，不然会显示不全
        self.label2.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px;  color: black")
        self.slider1.valueChanged.connect(lambda value: self.label2.setText(str("{:.1f}".format(value * 0.1))))

        #设置滑动条的最小值、最大值、当前值，放到后面是为了让上面的label2显示正确的值
        self.slider1.setMinimum(0)
        self.slider1.setMaximum(20)
        self.slider1.setValue(0)

        

        layout3.addWidget(label1)
        layout3.addWidget(label11)
        layout3.addStretch(1)  # 添加伸缩项
        layout3.addWidget(self.slider1)
        layout3.addWidget(self.label2)
        box3.setLayout(layout3)






        # -----创建第5个组，添加多个组件-----
        box5 = QGroupBox()
        box5.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout5 = QHBoxLayout()

        #设置“top_p”标签
        label4 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        label4.setText("Top_p")

        #设置“top_p”副标签
        label41 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label41.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 10px;  color: black")
        label41.setText("(官方默认值为1)")


        #设置“top_p”滑动条
        self.slider2 = Slider(Qt.Horizontal, self)
        self.slider2.setFixedWidth(200)


        # 创建一个QLabel控件，并设置初始文本为滑动条的初始值,并实时更新
        self.label5 = QLabel(str(self.slider2.value()), self)
        self.label5.setFixedSize(100, 15)  # 设置标签框的大小，不然会显示不全
        self.label5.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px;  color: black")
        self.slider2.valueChanged.connect(lambda value: self.label5.setText(str("{:.1f}".format(value * 0.1))))

        #设置滑动条的最小值、最大值、当前值，放在后面是为了让上面的label5显示正确的值和格式
        self.slider2.setMinimum(0)
        self.slider2.setMaximum(10)
        self.slider2.setValue(10)



        layout5.addWidget(label4)
        layout5.addWidget(label41)
        layout5.addStretch(1)  # 添加伸缩项
        layout5.addWidget(self.slider2)
        layout5.addWidget(self.label5)
        box5.setLayout(layout5)








        # -----创建第7个组，添加多个组件-----
        box7 = QGroupBox()
        box7.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout7 = QHBoxLayout()

        #设置“presence_penalty”标签
        label7 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label7.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        label7.setText("Presence_penalty")

        #设置“presence_penalty”副标签
        label71 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label71.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 10px;  color: black")
        label71.setText("(官方默认值为0)")


        #设置“presence_penalty”滑动条
        self.slider3 = Slider(Qt.Horizontal, self)
        self.slider3.setFixedWidth(200)

        # 创建一个QLabel控件，并设置初始文本为滑动条的初始值,并实时更新
        self.label8 = QLabel(str(self.slider3.value()), self)
        self.label8.setFixedSize(100, 15)  # 设置标签框的大小，不然会显示不全
        self.label8.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px;  color: black")
        self.slider3.valueChanged.connect(lambda value: self.label8.setText(str("{:.1f}".format(value * 0.1))))

        #设置滑动条的最小值、最大值、当前值，放到后面是为了让上面的label8显示正确的值和格式
        self.slider3.setMinimum(-20)
        self.slider3.setMaximum(20)
        self.slider3.setValue(0)



        layout7.addWidget(label7)
        layout7.addWidget(label71)
        layout7.addStretch(1)  # 添加伸缩项
        layout7.addWidget(self.slider3)
        layout7.addWidget(self.label8)
        box7.setLayout(layout7)






        # -----创建第9个组，添加多个组件-----
        box9 = QGroupBox()
        box9.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout9 = QHBoxLayout()

        #设置“frequency_penalty”标签
        label9 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label9.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        label9.setText("Frequency_penalty")

        #设置“presence_penalty”副标签
        label91 = QLabel(parent=self, flags=Qt.WindowFlags())  
        label91.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 10px;  color: black")
        label91.setText("(官方默认值为0)")

        #设置“frequency_penalty”滑动条
        self.slider4 = Slider(Qt.Horizontal, self)
        self.slider4.setFixedWidth(200)

        # 创建一个QLabel控件，并设置初始文本为滑动条的初始值,并实时更新
        self.label10 = QLabel(str(self.slider4.value()), self)
        self.label10.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 12px;  color: black")
        self.label10.setFixedSize(100, 15)  # 设置标签框的大小，不然会显示不全
        self.slider4.valueChanged.connect(lambda value: self.label10.setText(str("{:.1f}".format(value * 0.1))))

        #设置滑动条的最小值、最大值、当前值，放到后面是为了让上面的label10显示正确的值和格式
        self.slider4.setMinimum(-20)
        self.slider4.setMaximum(20)
        self.slider4.setValue(0)


        layout9.addWidget(label9)
        layout9.addWidget(label91)
        layout9.addStretch(1)  # 添加伸缩项
        layout9.addWidget(self.slider4)
        layout9.addWidget(self.label10)
        box9.setLayout(layout9)





        # 把内容添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box1)
        container.addWidget(box3)
        container.addWidget(box5)
        container.addWidget(box7)
        container.addWidget(box9)
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下

