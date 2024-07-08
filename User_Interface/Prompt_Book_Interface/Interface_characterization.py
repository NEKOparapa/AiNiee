

from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar

class Widget_characterization(QFrame): # 角色介绍页面

    def __init__(self, text: str, parent=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用

        # 最外层的垂直布局
        container = QVBoxLayout()

        # -----创建第1个组，添加放置表格-----
        self.tableView = TableWidget(self)
        self.tableView.setWordWrap(False) #设置表格内容不换行
        self.tableView.setRowCount(2) #设置表格行数
        self.tableView.setColumnCount(7) #设置表格列数
        #self.tableView.verticalHeader().hide() #隐藏垂直表头
        self.tableView.setHorizontalHeaderLabels(['原名', '译名', '性别', '年龄', '性格', '说话风格', '补充']) #设置水平表头
        self.tableView.resizeColumnsToContents() #设置列宽度自适应内容
        self.tableView.resizeRowsToContents() #设置行高度自适应内容
        self.tableView.setEditTriggers(QAbstractItemView.AllEditTriggers)   # 设置所有单元格可编辑
        #self.tableView.setFixedSize(500, 300)         # 设置表格大小
        self.tableView.setMaximumHeight(400)          # 设置表格的最大高度
        self.tableView.setMinimumHeight(400)             # 设置表格的最小高度
        self.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  #作用是将表格填满窗口
        #self.tableView.setSortingEnabled(True)  #设置表格可排序

        # 在表格最后一行第一列添加"添加行"按钮
        button = PushButton('添新行')
        self.tableView.setCellWidget(self.tableView.rowCount()-1, 0, button)
        button.clicked.connect(self.add_row)
        # 在表格最后一行第三列添加"删除空白行"按钮
        button = PushButton('删空行')
        self.tableView.setCellWidget(self.tableView.rowCount()-1, 6, button)
        button.clicked.connect(self.delete_blank_row)


        # -----创建第3个组，添加多个组件-----
        box3 = QGroupBox()
        box3.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout3 = QHBoxLayout()

        #设置“译时提示”标签
        label3 = QLabel( flags=Qt.WindowFlags())  
        label3.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")
        label3.setText("添加角色设定")

        #设置“译时提示”显示
        self.label4 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px;  color: black")
        self.label4.setText("(文本中出现了角色原名触发)")


        #设置“译时提示”开
        self.checkBox1 = CheckBox('启用功能')
        #self.checkBox2.stateChanged.connect(self.checkBoxChanged2)

        layout3.addWidget(label3)
        layout3.addWidget(self.label4)
        layout3.addStretch(1)  # 添加伸缩项
        layout3.addWidget(self.checkBox1)
        box3.setLayout(layout3)


        # 把内容添加到容器中
        container.addWidget(box3)    
        container.addWidget(self.tableView)
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        #self.scrollWidget.setLayout(container)
        self.setLayout(container)
        container.setSpacing(20)     
        container.setContentsMargins(50, 70, 50, 30)      


    #添加行按钮
    def add_row(self):
        # 添加新行在按钮所在行前面
        self.tableView.insertRow(self.tableView.rowCount()-1)
        #设置新行的高度与前一行相同
        self.tableView.setRowHeight(self.tableView.rowCount()-2, self.tableView.rowHeight(self.tableView.rowCount()-3))

    #删除空白行按钮
    def delete_blank_row(self):
        # 从倒数第二行开始反向遍历表格，因为最后一行是按钮行
        for i in range(self.tableView.rowCount() - 2, -1, -1):
            # 检查第一列和第二列是否为空
            item1 = self.tableView.item(i, 0)
            item2 = self.tableView.item(i, 1)
            if (item1 is None or item1.text() == '') and (item2 is None or item2.text() == ''):
                self.tableView.removeRow(i)
