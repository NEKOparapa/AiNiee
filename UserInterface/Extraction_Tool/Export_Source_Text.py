import os
import yaml

from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import CheckBox
from qfluentwidgets import FluentIcon
from qfluentwidgets import PushButton
from qfluentwidgets import HyperlinkButton
from qfluentwidgets import StrongBodyLabel
from qfluentwidgets import PrimaryPushButton

class Widget_export_source_text(QFrame):#  提取子界面
    def __init__(self, text: str, parent=None,jtpp=None):#解释器会自动调用这个函数
        super().__init__(parent=parent)          #调用父类的构造函数
        self.setObjectName(text.replace(' ', '-'))#设置对象名，作用是在NavigationInterface中的addItem中的routeKey参数中使用
        self.jtpp = jtpp
        #设置各个控件-----------------------------------------------------------------------------------------



        # -----创建第1个组，添加多个组件-----
        box = QGroupBox()
        layout = QHBoxLayout()


        self.labe1_3 = StrongBodyLabel()
        self.labe1_3.setText("RPG Maker MV/MZ 的文本提取注入工具")


        #设置官方文档说明链接按钮
        hyperlinkButton = HyperlinkButton(
            url='https://www.ai2.moe/topic/10271-%E8%87%AA%E5%88%9B%E5%B7%A5%E5%85%B7%E7%BF%BB%E8%AF%91%E5%B7%A5%E5%85%B7rpg%E7%BF%BB%E8%AF%91jt%EF%BC%8C%E7%9B%AE%E6%A0%87%E6%98%AF%E9%9B%B6%E9%97%A8%E6%A7%9B%E7%9A%84%EF%BC%8C%E5%86%85%E5%B5%8C%E4%BA%86%E5%A4%9A%E4%B8%AA%E8%84%9A%E6%9C%AC%E7%9A%84%E9%9D%92%E6%98%A5%E7%89%88t214%E5%BA%A6%E7%9B%98/',
            text='(使用说明)'
        )


        layout.addStretch(1)  # 添加伸缩项
        layout.addWidget(self.labe1_3)
        layout.addWidget(hyperlinkButton)
        layout.addStretch(1)  # 添加伸缩项
        box.setLayout(layout)




        # -----创建第1个组，添加多个组件-----
        box_switch = QGroupBox()
        layout_switch = QHBoxLayout()

        #设置“是否日语游戏”标签
        self.labe1_4 = StrongBodyLabel()
        self.labe1_4.setText("是否日语游戏")



        # 设置“是否日语游戏”选择开关
        self.SwitchButton_ja = CheckBox('        ')
        self.SwitchButton_ja.setChecked(True)
        # 绑定选择开关的点击事件
        self.SwitchButton_ja.clicked.connect(self.test)



        layout_switch.addWidget(self.labe1_4)
        layout_switch.addStretch(1)  # 添加伸缩项
        layout_switch.addWidget(self.SwitchButton_ja)
        box_switch.setLayout(layout_switch)



        # -----创建第2个组，添加多个组件-----
        box_input = QGroupBox()
        layout_input = QHBoxLayout()

        #设置“游戏文件夹”标签
        label4 = StrongBodyLabel()
        label4.setText("游戏文件夹")

        #设置“游戏文件夹”显示
        self.label_input_path = StrongBodyLabel()
        self.label_input_path.setText("(游戏根目录文件夹)")

        #设置打开文件按钮
        self.pushButton_input = PushButton('选择文件夹', self, FluentIcon.FOLDER)
        self.pushButton_input.clicked.connect(self.Select_project_folder) #按钮绑定槽函数



        layout_input.addWidget(label4)
        layout_input.addWidget(self.label_input_path)
        layout_input.addStretch(1)  # 添加伸缩项
        layout_input.addWidget(self.pushButton_input)
        box_input.setLayout(layout_input)



        # -----创建第3个组，添加多个组件-----
        box_output = QGroupBox()
        layout_output = QHBoxLayout()

        #设置“输出文件夹”标签
        label6 = StrongBodyLabel()
        label6.setText("原文存储文件夹")

        #设置“输出文件夹”显示
        self.label_output_path = StrongBodyLabel()
        self.label_output_path.setText("(游戏原文提取后存放的文件夹)")

        #设置输出文件夹按钮
        self.pushButton_output = PushButton('选择文件夹', self, FluentIcon.FOLDER)
        self.pushButton_output.clicked.connect(self.Select_output_folder) #按钮绑定槽函数


        layout_output.addWidget(label6)
        layout_output.addWidget(self.label_output_path)
        layout_output.addStretch(1)  # 添加伸缩项
        layout_output.addWidget(self.pushButton_output)
        box_output.setLayout(layout_output)



        # -----创建第3个组，添加多个组件-----
        box_data = QGroupBox()
        layout_data = QHBoxLayout()

        #设置“输出文件夹”标签
        label6 = StrongBodyLabel()
        label6.setText("工程存储文件夹")

        #设置“输出文件夹”显示
        self.label_data_path = StrongBodyLabel()
        self.label_data_path.setText("(该游戏工程数据存放的文件夹)")

        #设置输出文件夹按钮
        self.pushButton_data = PushButton('选择文件夹', self, FluentIcon.FOLDER)
        self.pushButton_data.clicked.connect(self.Select_data_folder) #按钮绑定槽函数


        layout_data.addWidget(label6)
        layout_data.addWidget(self.label_data_path)
        layout_data.addStretch(1)  # 添加伸缩项
        layout_data.addWidget(self.pushButton_data)
        box_data.setLayout(layout_data)





        # -----创建第x个组，添加多个组件-----
        box_start_export = QGroupBox()
        layout_start_export = QHBoxLayout()


        #设置“开始翻译”的按钮
        self.primaryButton_start_export = PrimaryPushButton('开始提取原文', self, FluentIcon.UPDATE)
        self.primaryButton_start_export.clicked.connect(self.Start_export) #按钮绑定槽函数


        layout_start_export.addStretch(1)  # 添加伸缩项
        layout_start_export.addWidget(self.primaryButton_start_export)
        layout_start_export.addStretch(1)  # 添加伸缩项
        box_start_export.setLayout(layout_start_export)



        # 最外层的垂直布局
        container = QVBoxLayout()

        # 把内容添加到容器中
        container.addStretch(1)  # 添加伸缩项
        container.addWidget(box)
        container.addWidget(box_switch)
        container.addWidget(box_input)
        container.addWidget(box_output)
        container.addWidget(box_data)
        container.addWidget(box_start_export)
        container.addStretch(1)  # 添加伸缩项

        # 设置窗口显示的内容是最外层容器
        self.setLayout(container)
        container.setSpacing(28) # 设置布局内控件的间距为28
        container.setContentsMargins(50, 70, 50, 30) # 设置布局的边距, 也就是外边框距离，分别为左、上、右、下

    #设置开关绑定函数
    def test(self, isChecked: bool):
        if isChecked== False:
            print("[INFO] 不建议使用在非日语游戏上,容易出现问题")

    # 选择输入文件夹按钮绑定函数
    def Select_project_folder(self):
        label_input_path = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if label_input_path:
            self.label_input_path.setText(label_input_path)
            print('[INFO] 已选择游戏根目录文件夹: ',label_input_path)
        else :
            print('[INFO] 未选择文件夹')
            return  # 直接返回，不执行后续操作


    # 选择原文文件夹按钮绑定函数
    def Select_output_folder(self):
        label_output_path = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if label_output_path:
            self.label_output_path.setText(label_output_path)
            print('[INFO] 已选择原文存储文件夹:' ,label_output_path)
        else :
            print('[INFO] 未选择文件夹')
            return  # 直接返回，不执行后续操作


    # 选择工程文件夹按钮绑定函数
    def Select_data_folder(self):
        data_Folder = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
        if data_Folder:
            self.label_data_path.setText(data_Folder)
            print('[INFO] 已选择工程存储文件夹:' ,data_Folder)
        else :
            print('[INFO] 未选择文件夹')
            return  # 直接返回，不执行后续操作


    # 提取函数
    def Start_export(self):
        print('[INFO] 开始提取游戏原文,请耐心等待！！！')

        #读取配置文件
        # 方法: 使用 os.path.join()
        # 获取 AiNiee.py 所在目录
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # 构建 config.yaml 的完整路径, StevExtraction 在 AiNiee 的子目录下
        config_path = os.path.join(current_dir, "StevExtraction", "config.yaml")

        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        #修改输入输出路径及开关
        config['game_path'] = self.label_input_path.text()
        config['save_path'] = self.label_data_path.text()
        config['data_path'] = self.label_output_path.text()
        config['ja']=self.SwitchButton_ja.isChecked()
        #提取文本
        pj=self.jtpp.Jr_Tpp(config)
        pj.FromGame(config['game_path'],config['save_path'],config['data_path'])