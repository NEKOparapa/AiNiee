
from PyQt5.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QPainter, QPixmap#需要安装库 pip3 install PyQt5
from PyQt5.QtCore import  QObject,  QRect,  QUrl,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QAbstractItemView,QHeaderView,QApplication, QTableWidgetItem, QFrame, QGridLayout, QGroupBox, QLabel,QFileDialog, QStackedWidget, QHBoxLayout, QVBoxLayout

from qfluentwidgets.components import Dialog  # 需要安装库 pip install "PyQt-Fluent-Widgets[full]" -i https://pypi.org/simple/
from qfluentwidgets import ProgressRing, SegmentedWidget, TableWidget,CheckBox, DoubleSpinBox, HyperlinkButton,InfoBar, InfoBarPosition, NavigationWidget, Slider, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, SwitchButton, TextEdit, Theme, TransparentTogglePushButton,  setTheme ,isDarkTheme,qrouter,NavigationInterface,NavigationItemPosition, EditableComboBox
from qfluentwidgets import FluentIcon as FIF
from qframelesswindow import FramelessWindow, StandardTitleBar



class Widget_New_proxy(QFrame):  # 代理账号主界面
    def __init__(self, text: str, parent=None,configurator=None,user_interface_prompter=None,background_executor=None):  # 构造函数，初始化实例时会自动调用
        super().__init__(parent=parent)  # 调用父类 QWidget 的构造函数
        self.setObjectName(text.replace(' ', '-'))  # 设置对象名，用于在 NavigationInterface 中的 addItem 方法中的 routeKey 参数中使用
        self.configurator = configurator
        self.user_interface_prompter = user_interface_prompter
        self.background_executor = background_executor


        self.pivot = SegmentedWidget(self)  # 创建一个 SegmentedWidget 实例，分段式导航栏
        self.stackedWidget = QStackedWidget(self)  # 创建一个 QStackedWidget 实例，堆叠式窗口
        self.vBoxLayout = QVBoxLayout(self)  # 创建一个垂直布局管理器

        # 传递对象名
        text = text.replace(' ', '-')

        self.A_settings = Widget_Proxy_A('A_settings', self,configurator,user_interface_prompter,background_executor,text)  # 创建实例，指向界面
        self.B_settings = Widget_Proxy_B('B_settings', self,configurator,user_interface_prompter,background_executor)  # 创建实例，指向界面

        # 添加子界面到分段式导航栏
        self.addSubInterface(self.A_settings, 'A_settings', '代理设置')
        self.addSubInterface(self.B_settings, 'B_settings', '速率价格设置')

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


class Widget_Proxy_A(QFrame):#  代理账号基础设置子界面
    def __init__(self, text: str, parent=None,configurator=None,user_interface_prompter=None,background_executor=None,ObjectName=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.configurator = configurator
        self.user_interface_prompter = user_interface_prompter
        self.background_executor = background_executor
        self.ObjectName = ObjectName
        #设置各个控件-----------------------------------------------------------------------------------------

        # -----创建第x个组，添加多个组件-----
        box_auto_complete = QGroupBox()
        box_auto_complete.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout1_auto_complete = QHBoxLayout()

        # 设置标签
        labe1_6 = QLabel(flags=Qt.WindowFlags())  
        labe1_6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px")
        labe1_6.setText("请求地址自动补全")

        # 设置选择开关
        self.SwitchButton_auto_complete = SwitchButton(parent=self)    
        self.SwitchButton_auto_complete.setChecked(True)


        layout1_auto_complete.addWidget(labe1_6)
        layout1_auto_complete.addStretch(1)  # 添加伸缩项
        layout1_auto_complete.addWidget(self.SwitchButton_auto_complete)
        box_auto_complete.setLayout(layout1_auto_complete)


        # -----创建第1个组，添加多个组件-----
        box_relay_address = QGroupBox()
        box_relay_address.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_relay_address = QHBoxLayout()

        #设置“中转地址”标签
        self.labelA = QLabel( flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.labelA.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.labelA.setText("中转请求地址(URL)")

        #设置微调距离用的空白标签
        self.labelB = QLabel()  
        self.labelB.setText("                ")

        #设置“中转地址”的输入框
        self.LineEdit_relay_address = LineEdit()
        #LineEdit1.setFixedSize(300, 30)


        layout_relay_address.addWidget(self.labelA)
        layout_relay_address.addWidget(self.labelB)
        layout_relay_address.addWidget(self.LineEdit_relay_address)
        box_relay_address.setLayout(layout_relay_address)




        # -----创建第2个组，添加多个组件-----
        box_proxy_platform = QGroupBox()
        box_proxy_platform.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_proxy_platform = QHBoxLayout()

        #设置标签
        self.label_proxy_platform = QLabel(flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label_proxy_platform.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.label_proxy_platform.setText("请求格式")


        #设置下拉选择框
        self.comboBox_proxy_platform = ComboBox() #以demo为父类
        self.comboBox_proxy_platform.addItems(['OpenAI', 'Anthropic'])
        self.comboBox_proxy_platform.setCurrentIndex(0) #设置下拉框控件（ComboBox）的当前选中项的索引为0，也就是默认选中第一个选项
        self.comboBox_proxy_platform.setFixedSize(250, 35)
        
        # 连接下拉框的currentTextChanged信号到相应的槽函数
        self.comboBox_proxy_platform.currentTextChanged.connect(self.on_combobox_changed)


        layout_proxy_platform.addWidget(self.label_proxy_platform)
        layout_proxy_platform.addStretch(1)
        layout_proxy_platform.addWidget(self.comboBox_proxy_platform)
        box_proxy_platform.setLayout(layout_proxy_platform)




     # -----创建第3个组，添加多个组件-----
        box_model = QGroupBox()
        box_model.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_model = QHBoxLayout()

        #设置“模型选择”标签
        self.label_model = QLabel(flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label_model.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.label_model.setText("模型选择(可编辑)")


        #设置“模型类型”下拉选择框
        self.comboBox_model_openai = EditableComboBox() #以demo为父类
        self.comboBox_model_openai.addItems(['gpt-3.5-turbo','gpt-3.5-turbo-0301','gpt-3.5-turbo-0613', 'gpt-3.5-turbo-1106', 'gpt-3.5-turbo-0125','gpt-3.5-turbo-16k', 'gpt-3.5-turbo-16k-0613',
                                 'gpt-4','gpt-4o','gpt-4o-mini','gpt-4-0314', 'gpt-4-0613','gpt-4-turbo','gpt-4-turbo-preview','gpt-4-1106-preview','gpt-4-0125-preview'])
        self.comboBox_model_openai.setCurrentIndex(0) #设置下拉框控件（ComboBox）的当前选中项的索引为0，也就是默认选中第一个选项
        self.comboBox_model_openai.setFixedSize(250, 35)


        self.comboBox_model_anthropic = EditableComboBox() #以demo为父类
        self.comboBox_model_anthropic.addItems(['claude-2.0','claude-2.1','claude-3-haiku-20240307','claude-3-sonnet-20240229', 'claude-3-opus-20240229','claude-3-5-sonnet-20240620'])
        self.comboBox_model_anthropic.setCurrentIndex(0) #设置下拉框控件（ComboBox）的当前选中项的索引为0，也就是默认选中第一个选项
        self.comboBox_model_anthropic.setFixedSize(250, 35)



        layout_model.addWidget(self.label_model)
        layout_model.addStretch(1)
        layout_model.addWidget(self.comboBox_model_openai)
        layout_model.addWidget(self.comboBox_model_anthropic)
        box_model.setLayout(layout_model)


        #设置默认显示的模型选择框，其余隐藏
        self.comboBox_model_openai.show()
        self.comboBox_model_anthropic.hide()


        # -----创建第3个组，添加多个组件-----
        box_apikey = QGroupBox()
        box_apikey.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_apikey = QHBoxLayout()

        #设置“API KEY”标签
        self.label_apikey = QLabel(flags=Qt.WindowFlags())  
        self.label_apikey.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")
        self.label_apikey.setText("API KEY")

        #设置微调距离用的空白标签
        self.labely = QLabel()  
        self.labely.setText("                       ")

        #设置“API KEY”的输入框
        self.TextEdit_apikey = TextEdit()



        # 追加到容器中
        layout_apikey.addWidget(self.label_apikey)
        layout_apikey.addWidget(self.labely)
        layout_apikey.addWidget(self.TextEdit_apikey)
        # 添加到 box中
        box_apikey.setLayout(layout_apikey)



        # -----创建第4个组，添加多个组件-----
        box_proxy_port = QGroupBox()
        box_proxy_port.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_proxy_port = QHBoxLayout()

        #设置“系统代理端口”标签
        self.label_proxy_port = QLabel( flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label_proxy_port.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.label_proxy_port.setText("系统代理")

        #设置微调距离用的空白标签
        self.label_null = QLabel()  
        self.label_null.setText("                      ")

        #设置“系统代理端口”的输入框
        self.LineEdit_proxy_port = LineEdit()
        #LineEdit1.setFixedSize(300, 30)


        layout_proxy_port.addWidget(self.label_proxy_port)
        layout_proxy_port.addWidget(self.label_null)
        layout_proxy_port.addWidget(self.LineEdit_proxy_port)
        box_proxy_port.setLayout(layout_proxy_port)



        # -----创建第5个组，添加多个组件-----
        box_test = QGroupBox()
        box_test.setStyleSheet(""" QGroupBox {border: 0px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_test = QHBoxLayout()


        #设置“测试请求”的按钮
        self.primaryButton_test = PrimaryPushButton('测试请求', self, FIF.SEND)
        self.primaryButton_test.clicked.connect(self.test_request) #按钮绑定槽函数


        #设置“删除配置”的按钮
        self.primaryButton_del = TransparentTogglePushButton('删除配置', self, FIF.DELETE)
        self.primaryButton_del.clicked.connect(self.del_config) #按钮绑定槽函数

        layout_test.addStretch(1)  # 添加伸缩项
        layout_test.addWidget(self.primaryButton_test)
        layout_test.addStretch(1)  # 添加伸缩项
        layout_test.addWidget(self.primaryButton_del)
        layout_test.addStretch(1)  # 添加伸缩项
        box_test.setLayout(layout_test)





        # -----最外层容器设置垂直布局-----
        container = QVBoxLayout()

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(20, 10, 20, 20) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下

        # 把各个组添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box_relay_address)
        container.addWidget(box_auto_complete)
        container.addWidget(box_proxy_platform)
        container.addWidget(box_model)
        container.addWidget(box_apikey)
        container.addWidget(box_proxy_port)
        container.addWidget(box_test)
        container.addStretch(1)  # 添加伸缩项




    def on_combobox_changed(self, index):
        # 根据下拉框的索引调用不同的函数
        if index =="OpenAI":
            self.comboBox_model_openai.show()
            self.comboBox_model_anthropic.hide()
        elif index == 'Anthropic':
            self.comboBox_model_openai.hide()
            self.comboBox_model_anthropic.show()


    def del_config(self):
        object_name = self.ObjectName
        self.user_interface_prompter.del_proxy_option(object_name)

        self.user_interface_prompter.createSuccessInfoBar("已删除该平台配置,请勿重复点击按钮")


    def test_request(self):

        if self.background_executor.Request_test_switch(self):
            Base_url = self.LineEdit_relay_address.text()      # 获取代理地址
            Proxy_platform = self.comboBox_proxy_platform.currentText()  # 获取代理平台
            API_key_str = self.TextEdit_apikey.toPlainText()        # 获取apikey输入值
            Proxy_port = self.LineEdit_proxy_port.text()            # 获取代理端口
            op_auto_complete = self.SwitchButton_auto_complete.isChecked()

            if Proxy_platform == "OpenAI":
                Model_Type = self.comboBox_model_openai.currentText()

                # openai接口特有的自动补全
                if op_auto_complete:
                    if Base_url[-3:] != "/v1" and Base_url[-3:] != "/v4" and Base_url[-3:] != "/v3" :
                        Base_url = Base_url + "/v1"

            elif Proxy_platform == "Anthropic":
                Model_Type = self.comboBox_model_anthropic.currentText()

            #创建子线程
            thread = self.background_executor("接口测试","","",Proxy_platform,Base_url,Model_Type,API_key_str,Proxy_port)
            thread.start()



class Widget_Proxy_B(QFrame):#  代理账号进阶设置子界面
    def __init__(self, text: str, parent=None,configurator=None,user_interface_prompter=None,background_executor=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.configurator = configurator
        self.user_interface_prompter = user_interface_prompter
        self.background_executor = background_executor
        #设置各个控件-----------------------------------------------------------------------------------------


        # -----创建第1个组(后面加的)，添加多个组件-----
        box_tokens = QGroupBox()
        box_tokens.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_tokens = QHBoxLayout()

        #设置标签
        self.label_tokens = QLabel( flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label_tokens.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.label_tokens.setText("每次发送文本上限")

        #设置“说明”显示
        self.labelA_tokens = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.labelA_tokens.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px")
        self.labelA_tokens.setText("(tokens)")  

        #数值输入
        self.spinBox_tokens = SpinBox(self)
        self.spinBox_tokens.setRange(0, 2147483647)    
        self.spinBox_tokens.setValue(4000)


        layout_tokens.addWidget(self.label_tokens)
        layout_tokens.addWidget(self.labelA_tokens)
        layout_tokens.addStretch(1)  # 添加伸缩项
        layout_tokens.addWidget(self.spinBox_tokens)
        box_tokens.setLayout(layout_tokens)



        # -----创建第1个组(后面加的)，添加多个组件-----
        box_RPM = QGroupBox()
        box_RPM.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_RPM = QHBoxLayout()

        #设置“RPM”标签
        self.labelY = QLabel( flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.labelY.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.labelY.setText("每分钟请求数")

        #设置“说明”显示
        self.labelA = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.labelA.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px")
        self.labelA.setText("(RPM)")  

        #数值输入
        self.spinBox_RPM = SpinBox(self)
        self.spinBox_RPM.setRange(0, 2147483647)    
        self.spinBox_RPM.setValue(3500)


        layout_RPM.addWidget(self.labelY)
        layout_RPM.addWidget(self.labelA)
        layout_RPM.addStretch(1)  # 添加伸缩项
        layout_RPM.addWidget(self.spinBox_RPM)
        box_RPM.setLayout(layout_RPM)



        # -----创建第2个组（后面加的），添加多个组件-----
        box_TPM = QGroupBox()
        box_TPM.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_TPM = QHBoxLayout()

        #设置“TPM”标签
        self.labelB = QLabel( flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.labelB.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.labelB.setText("每分钟tokens数")
    
        #设置“说明”显示
        self.labelC = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.labelC.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px")
        self.labelC.setText("(TPM)") 

        #数值输入
        self.spinBox_TPM = SpinBox(self)
        self.spinBox_TPM.setRange(0, 2147483647)    
        self.spinBox_TPM.setValue(60000)


        layout_TPM.addWidget(self.labelB)
        layout_TPM.addWidget(self.labelC)
        layout_TPM.addStretch(1)  # 添加伸缩项
        layout_TPM.addWidget(self.spinBox_TPM)
        box_TPM.setLayout(layout_TPM)


        # -----创建第3个组（后面加的），添加多个组件-----
        box_input_pricing = QGroupBox()
        box_input_pricing.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_input_pricing = QHBoxLayout()

        #设置“请求输入价格”标签
        self.labelD = QLabel( flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.labelD.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.labelD.setText("请求输入价格")
    
        #设置“说明”显示
        self.labelE = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.labelE.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px")
        self.labelE.setText("( /1K tokens)") 

        #数值输入
        self.spinBox_input_pricing = DoubleSpinBox(self)
        self.spinBox_input_pricing.setRange(0.0000, 2147483647)   
        self.spinBox_input_pricing.setDecimals(4)  # 设置小数点后的位数 
        self.spinBox_input_pricing.setValue(0.0015)


        layout_input_pricing.addWidget(self.labelD)
        layout_input_pricing.addWidget(self.labelE)
        layout_input_pricing.addStretch(1)  # 添加伸缩项
        layout_input_pricing.addWidget(self.spinBox_input_pricing)
        box_input_pricing.setLayout(layout_input_pricing)


        # -----创建第4个组（后面加的），添加多个组件-----
        box_output_pricing = QGroupBox()
        box_output_pricing.setStyleSheet(""" QGroupBox {border: 1px solid lightgray; border-radius: 8px;}""")#分别设置了边框大小，边框颜色，边框圆角
        layout_output_pricing = QHBoxLayout()

        #设置“TPM”标签
        self.labelF = QLabel( flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.labelF.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;")#设置字体，大小，颜色
        self.labelF.setText("回复输出价格")
    
        #设置“说明”显示
        self.labelG = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.labelG.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 11px")
        self.labelG.setText("( /1K tokens)") 

        #数值输入
        self.spinBox_output_pricing = DoubleSpinBox(self)
        self.spinBox_output_pricing.setRange(0.0000, 2147483647)
        self.spinBox_output_pricing.setDecimals(4)  # 设置小数点后的位数     
        self.spinBox_output_pricing.setValue(0.002)
        

        layout_output_pricing.addWidget(self.labelF)
        layout_output_pricing.addWidget(self.labelG)
        layout_output_pricing.addStretch(1)  # 添加伸缩项
        layout_output_pricing.addWidget(self.spinBox_output_pricing)
        box_output_pricing.setLayout(layout_output_pricing)



        # -----最外层容器设置垂直布局-----
        container = QVBoxLayout()

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(20, 10, 20, 20) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下

        # 把各个组添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box_tokens)
        container.addWidget(box_RPM)
        container.addWidget(box_TPM)
        container.addWidget(box_input_pricing)
        container.addWidget(box_output_pricing)
        container.addStretch(1)  # 添加伸缩项
