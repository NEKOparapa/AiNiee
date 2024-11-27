import os
import yaml

from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import SpinBox
from qfluentwidgets import LineEdit
from qfluentwidgets import CheckBox
from qfluentwidgets import FluentIcon
from qfluentwidgets import PushButton
from qfluentwidgets import StrongBodyLabel
from qfluentwidgets import PrimaryPushButton


class Widget_import_translated_text(QFrame):#  导入子界面
    def __init__(self, text: str, parent=None, jtpp=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.jtpp = jtpp
        #设置各个控件-----------------------------------------------------------------------------------------



        # -----创建第1个组，添加多个组件-----
        box_input = QGroupBox()
        layout_input = QHBoxLayout()

        #设置“输入文件夹”标签
        label4 = StrongBodyLabel()
        label4.setText("游戏文件夹")

        #设置“输入文件夹”显示
        self.label_input_path = StrongBodyLabel()
        self.label_input_path.setText("(原来的游戏根目录文件夹)")

        #设置打开文件按钮
        self.pushButton_input = PushButton('选择文件夹', self, FluentIcon.FOLDER)
        self.pushButton_input.clicked.connect(self.Select_game_folder) #按钮绑定槽函数



        layout_input.addWidget(label4)
        layout_input.addWidget(self.label_input_path)
        layout_input.addStretch(1)  # 添加伸缩项
        layout_input.addWidget(self.pushButton_input)
        box_input.setLayout(layout_input)



        # -----创建第2个组，添加多个组件-----
        box_data = QGroupBox()
        layout_data = QHBoxLayout()

        #设置“输入文件夹”标签
        label4 = StrongBodyLabel()
        label4.setText("工程文件夹")

        #设置“输入文件夹”显示
        self.label_data_path = StrongBodyLabel()
        self.label_data_path.setText("(原来导出的工程数据文件夹)")

        #设置打开文件按钮
        self.pushButton_data = PushButton('选择文件夹', self, FluentIcon.FOLDER)
        self.pushButton_data.clicked.connect(self.Select_data_folder) #按钮绑定槽函数



        layout_data.addWidget(label4)
        layout_data.addWidget(self.label_data_path)
        layout_data.addStretch(1)  # 添加伸缩项
        layout_data.addWidget(self.pushButton_data)
        box_data.setLayout(layout_data)



        # -----创建第3个组，添加多个组件-----
        box_translation_folder = QGroupBox()
        layout_translation_folder = QHBoxLayout()

        #设置“输出文件夹”标签
        self.label6 = StrongBodyLabel()
        self.label6.setText("译文文件夹")

        #设置“输出文件夹”显示
        self.label_translation_folder = StrongBodyLabel()
        self.label_translation_folder.setText("(译文文件存放的文件夹)")

        #设置输出文件夹按钮
        self.pushButton_translation_folder = PushButton('选择文件夹', self, FluentIcon.FOLDER)
        self.pushButton_translation_folder.clicked.connect(self.Select_translation_folder) #按钮绑定槽函数


        layout_translation_folder.addWidget(self.label6)
        layout_translation_folder.addWidget(self.label_translation_folder)
        layout_translation_folder.addStretch(1)  # 添加伸缩项
        layout_translation_folder.addWidget(self.pushButton_translation_folder)
        box_translation_folder.setLayout(layout_translation_folder)


        # -----创建第4个组，添加多个组件-----
        box_output_folder = QGroupBox()
        layout_putput_folder = QHBoxLayout()

        #设置“输出文件夹”标签
        self.label7 = StrongBodyLabel()
        self.label7.setText("存储文件夹")

        #设置“输出文件夹”显示
        self.label_output_folder = StrongBodyLabel()
        self.label_output_folder.setText("(游戏文件注入译文后，存放的文件夹)")

        #设置输出文件夹按钮
        self.pushButton_putput_folder = PushButton('选择文件夹', self, FluentIcon.FOLDER)
        self.pushButton_putput_folder.clicked.connect(self.Select_save_folder) #按钮绑定槽函数


        layout_putput_folder.addWidget(self.label7)
        layout_putput_folder.addWidget(self.label_output_folder)
        layout_putput_folder.addStretch(1)  # 添加伸缩项
        layout_putput_folder.addWidget(self.pushButton_putput_folder)
        box_output_folder.setLayout(layout_putput_folder)



        # -----创建第5个组，添加多个组件-----
        box_title_watermark1 = QGroupBox()
        layout_title_watermark1 = QHBoxLayout()


        self.LineEdit_title_watermark = LineEdit()

        #设置微调距离用的空白标签
        self.labelB = StrongBodyLabel()
        self.labelB.setText("          ")

        # 设置“添加游戏标题水印”选择开关
        self.checkBox_title_watermark = CheckBox('添加标题水印', self)



        layout_title_watermark1.addWidget(self.LineEdit_title_watermark)
        layout_title_watermark1.addWidget(self.labelB)
        layout_title_watermark1.addWidget(self.checkBox_title_watermark)
        box_title_watermark1.setLayout(layout_title_watermark1)





        # -----创建第5个组，添加多个组件-----
        box_auto_wrap = QGroupBox()
        layout_auto_wrap = QHBoxLayout()

        #设置标签
        label4 = StrongBodyLabel()
        label4.setText("换行字数")

        self.spinBox_auto_wrap = SpinBox(self)
        self.spinBox_auto_wrap.setRange(0, 1000)
        self.spinBox_auto_wrap.setValue(0)


        # 设置“添加游戏标题水印”选择开关
        self.checkBox_auto_wrap = CheckBox('启用自动换行', self)


        layout_auto_wrap.addWidget(label4)
        layout_auto_wrap.addWidget(self.spinBox_auto_wrap)
        layout_auto_wrap.addStretch(1)
        layout_auto_wrap.addWidget(self.checkBox_auto_wrap)
        box_auto_wrap.setLayout(layout_auto_wrap)


        # -----创建第x个组，添加多个组件-----
        box_start_import = QGroupBox()
        layout_start_import = QHBoxLayout()


        #设置“开始翻译”的按钮
        self.primaryButton_start_import = PrimaryPushButton('开始注入译文', self, FluentIcon.UPDATE)
        self.primaryButton_start_import.clicked.connect(self.Start_import) #按钮绑定槽函数


        layout_start_import.addStretch(1)  # 添加伸缩项
        layout_start_import.addWidget(self.primaryButton_start_import)
        layout_start_import.addStretch(1)  # 添加伸缩项
        box_start_import.setLayout(layout_start_import)



        # 最外层的垂直布局
        container = QVBoxLayout()

        # 把内容添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box_input)
        container.addWidget(box_data)
        container.addWidget(box_translation_folder)
        container.addWidget(box_output_folder)
        container.addWidget(box_title_watermark1)
        container.addWidget(box_auto_wrap)
        container.addWidget(box_start_import)
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下


    # 选择输入文件夹按钮绑定函数
    def Select_game_folder(self):
        label_input_path = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if label_input_path:
            self.label_input_path.setText(label_input_path)
            print('[INFO] 已选择原游戏文件夹: ',label_input_path)
        else :
            print('[INFO] 未选择文件夹')
            return  # 直接返回，不执行后续操作

    # 选择工程文件夹按钮绑定函数
    def Select_data_folder(self):
        Data_Folder = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if Data_Folder:
            self.label_data_path.setText(Data_Folder)
            print('[INFO] 已选择工程数据文件夹: ',Data_Folder)
        else :
            print('[INFO] 未选择文件夹')
            return  # 直接返回，不执行后续操作

    # 选择译文文件夹按钮绑定函数
    def Select_translation_folder(self):
        translation_folder = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if translation_folder:
            self.label_translation_folder.setText(translation_folder)
            print('[INFO] 已选择译文文件夹:' ,translation_folder)
        else :
            print('[INFO] 未选择文件夹')
            return  # 直接返回，不执行后续操作

    # 选择存储文件夹按钮绑定函数
    def Select_save_folder(self):
        save_folder = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if save_folder:
            self.label_output_folder.setText(save_folder)
            print('[INFO] 已选择注入后存储文件夹:' ,save_folder)
        else :
            print('[INFO] 未选择文件夹')


    # 导入按钮绑定函数
    def Start_import(self):
        print('[INFO] 开始注入译文到游戏文件中,请耐心等待！！！')

        #读取配置文件
        config_path = ".\StevExtraction\config.yaml"
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        #修改配置信息
        config['game_path'] = self.label_input_path.text()
        config['save_path'] = self.label_data_path.text()
        config['translation_path'] = self.label_translation_folder.text()
        config['output_path'] = self.label_output_folder.text()

        if self.checkBox_title_watermark.isChecked():
            config['mark'] = self.LineEdit_title_watermark.text()
        else:
            config['mark'] = 0

        if self.checkBox_auto_wrap.isChecked():
            config['line_length'] = self.spinBox_auto_wrap.value()
        else:
            config['line_length'] = 0

        #导入文本
        pj=self.jtpp.Jr_Tpp(config,config['save_path'])
        pj.ToGame(config['game_path'],config['translation_path'],config['output_path'],config['mark'])

