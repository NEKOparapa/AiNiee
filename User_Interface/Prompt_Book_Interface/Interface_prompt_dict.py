
import json
import os
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar



class Widget_prompt_dict(QFrame): # 术语字典界面


    def __init__(self, text: str, parent=None,configurator=None,user_interface_prompter=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.configurator = configurator
        self.user_interface_prompter = user_interface_prompter
        # 最外层的垂直布局
        container = QVBoxLayout()

        # -----创建第1个组，添加放置表格-----
        self.tableView = TableWidget(self)
        self.tableView.setWordWrap(False) #设置表格内容不换行
        self.tableView.setRowCount(2) #设置表格行数
        self.tableView.setColumnCount(3) #设置表格列数
        #self.tableView.verticalHeader().hide() #隐藏垂直表头
        self.tableView.setHorizontalHeaderLabels(['原文', '译文', '备注']) #设置水平表头
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
        self.tableView.setCellWidget(self.tableView.rowCount()-1, 2, button)
        button.clicked.connect(self.delete_blank_row)



        # -----创建第1_1个组，添加多个组件-----
        box1_1 = QGroupBox()
        box1_1.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1_1 = QHBoxLayout()


        #设置导入字典按钮
        self.pushButton1 = PushButton('导入字典', self, FIF.DOWNLOAD)
        self.pushButton1.clicked.connect(self.Importing_dictionaries) #按钮绑定槽函数

        #设置导出字典按钮
        self.pushButton2 = PushButton('导出字典', self, FIF.SHARE)
        self.pushButton2.clicked.connect(self.Exporting_dictionaries) #按钮绑定槽函数

        #设置清空字典按钮
        self.pushButton3 = PushButton('清空字典', self, FIF.DELETE)
        self.pushButton3.clicked.connect(self.Empty_dictionary) #按钮绑定槽函数

        #设置保存字典按钮
        self.pushButton4 = PushButton('保存字典', self, FIF.SAVE)
        self.pushButton4.clicked.connect(self.Save_dictionary) #按钮绑定槽函数


        layout1_1.addWidget(self.pushButton1)
        layout1_1.addStretch(1)  # 添加伸缩项
        layout1_1.addWidget(self.pushButton2)
        layout1_1.addStretch(1)  # 添加伸缩项
        layout1_1.addWidget(self.pushButton3)
        layout1_1.addStretch(1)  # 添加伸缩项
        layout1_1.addWidget(self.pushButton4)
        box1_1.setLayout(layout1_1)




        # -----创建第3个组，添加多个组件-----
        box3 = QGroupBox()
        box3.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout3 = QHBoxLayout()

        #设置“译时提示”标签
        label3 = QLabel( flags=Qt.WindowFlags())  
        label3.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")
        label3.setText("添加提示字典")

        #设置“译时提示”显示
        self.label4 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label4.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px;  color: black")
        self.label4.setText("(原文触发，自动构建术语表)")


        #设置“译时提示”开
        self.checkBox2 = CheckBox('启用功能')
        self.checkBox2.stateChanged.connect(self.checkBoxChanged2)

        layout3.addWidget(label3)
        layout3.addWidget(self.label4)
        layout3.addStretch(1)  # 添加伸缩项
        layout3.addWidget(self.checkBox2)
        box3.setLayout(layout3)


        # 把内容添加到容器中
        container.addWidget(box3)    
        container.addWidget(self.tableView)
        container.addWidget(box1_1)
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
        #表格行数大于2时，删除表格内第一列和第二列为空或者空字符串的行
        if self.tableView.rowCount() > 2:
            # 删除表格内第一列和第二列为空或者空字符串的行
            for i in range(self.tableView.rowCount()-1):
                if self.tableView.item(i, 0) is None or self.tableView.item(i, 0).text() == '':
                    self.tableView.removeRow(i)
                    break
                elif self.tableView.item(i, 1) is None or self.tableView.item(i, 1).text() == '':
                    self.tableView.removeRow(i)
                    break

    # 将条目添加到表格的辅助函数
    def add_to_table(self, srt, dst, info):
            row = self.tableView.rowCount() - 1 #获取表格的倒数行数
            self.tableView.insertRow(row)    # 在表格中插入一行
            self.tableView.setItem(row, 0, QTableWidgetItem(srt))
            self.tableView.setItem(row, 1, QTableWidgetItem(dst))
            if info:
                self.tableView.setItem(row, 2, QTableWidgetItem(info))
            #设置新行的高度与前一行相同
            self.tableView.setRowHeight(row, self.tableView.rowHeight(row-1))

    #导入字典按钮
    def Importing_dictionaries(self):
        # 选择文件
        Input_File, _ = QFileDialog.getOpenFileName(None, 'Select File', '', 'JSON Files (*.json)')      #调用QFileDialog类里的函数来选择文件
        if Input_File:
            print(f'[INFO]  已选择字典导入文件: {Input_File}')
        else :
            print('[INFO]  未选择文件')
            return
        
        # 读取文件
        with open(Input_File, 'r', encoding="utf-8") as f:
            dictionary = json.load(f)

        # 检查数据是列表还是字典
        if isinstance(dictionary, list):  # 如果是列表
            for item in dictionary:
                if item.get("srt", "") and item.get("dst", ""):
                    srt = item.get("srt", "")
                    dst = item.get("dst", "")
                    info = item.get("info", "")

                    self.add_to_table(srt, dst,info)
                    # 格式例
                    # [
                    #   {
                    #     "srt": "xxxx",
                    #     "dst": "xxxx",
                    #     "info": "xxx",
                    #   }
                    # ]
                else: # 代表是Paratranz的术语表，处理每一个字典项
                    key = item.get("term", "")
                    value = item.get("translation", "")
                    info = ""
                    self.add_to_table(key, value,info)
                    # 格式例
                    # [
                    #   {
                    #     "id": 359894,
                    #     "createdAt": "2024-04-06T18:43:56.075Z",
                    #     "updatedAt": "2024-04-06T18:43:56.075Z",
                    #     "updatedBy": null,
                    #     "pos": "noun",
                    #     "uid": 49900,
                    #     "term": "アイテム",
                    #     "translation": "道具",
                    #     "note": "",
                    #     "project": 9841,
                    #     "variants": []
                    #   }
                    # ]
        elif isinstance(dictionary, dict):  # 如果是字典，处理字典键值对
            for key, value in dictionary.items():
                info = ""
                self.add_to_table(key, value,info)
        else:
            print('[ERROR]  不支持的文件格式')
            return

        self.user_interface_prompter.createSuccessInfoBar("导入成功")
        print(f'[INFO]  已导入字典文件')
    
    #导出字典按钮
    def Exporting_dictionaries(self):
        #获取表格中从第一行到倒数第二行的数据，判断第一列或第二列是否为空，如果为空则不获取。如果不为空，则第一列作为key，第二列作为value，存储中间字典中
        dictionary = []
        for row in range(self.tableView.rowCount() - 1):
            key_item = self.tableView.item(row, 0)
            value_item = self.tableView.item(row, 1)
            info_item = self.tableView.item(row, 2)
            if key_item and value_item:
                key = key_item.text()
                value = value_item.text()
                if info_item:
                    info = info_item.text()
                    dictionary.append({"srt":key,"dst":value,"info":info})
                else:
                    dictionary.append({"srt":key,"dst":value})


        # 选择文件保存路径
        Output_Folder = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if Output_Folder:
            print(f'[INFO]  已选择字典导出文件夹: {Output_Folder}')
        else :
            print('[INFO]  未选择文件夹')
            return  # 直接返回，不执行后续操作

        # 将字典保存到文件中
        with open(os.path.join(Output_Folder, "用户提示字典.json"), 'w', encoding="utf-8") as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=4)

        self.user_interface_prompter.createSuccessInfoBar("导出成功")
        print(f'[INFO]  已导出字典文件')

    #清空字典按钮
    def Empty_dictionary(self):
        #清空表格
        self.tableView.clearContents()
        #设置表格的行数为1
        self.tableView.setRowCount(2)
        
        # 在表格最后一行第一列添加"添加行"按钮
        button = PushButton('添新行')
        self.tableView.setCellWidget(self.tableView.rowCount()-1, 0, button)
        button.clicked.connect(self.add_row)
        # 在表格最后一行第三列添加"删除空白行"按钮
        button = PushButton('删空行')
        self.tableView.setCellWidget(self.tableView.rowCount()-1, 2, button)
        button.clicked.connect(self.delete_blank_row)

        self.user_interface_prompter.createSuccessInfoBar("清空成功")
        print(f'[INFO]  已清空字典')

    #保存字典按钮
    def Save_dictionary(self):
        self.user_interface_prompter.read_write_config("write",self.configurator.resource_dir)
        self.user_interface_prompter.createSuccessInfoBar("保存成功")
        print(f'[INFO]  已保存字典')

    
    #消息提示函数
    def checkBoxChanged2(self, isChecked: bool):
        if isChecked :
            self.user_interface_prompter.createSuccessInfoBar("已开启译时提示功能,将根据发送文本自动添加翻译示例")
