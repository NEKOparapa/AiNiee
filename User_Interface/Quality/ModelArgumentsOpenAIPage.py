from PyQt5.Qt import Qt
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import HyperlinkLabel

from AiNieeBase import AiNieeBase
from Widget.SliderCard import SliderCard
from Widget.SwitchButtonCard import SwitchButtonCard

class ModelArgumentsOpenAIPage(QFrame, AiNieeBase):

    DEFAULT = {
        "OpenAI_parameter_adjustment": False,
        "OpenAI_top_p": 10,
        "OpenAI_Temperature": 10,
        "OpenAI_presence_penalty": 0,
        "OpenAI_frequency_penalty": 0,
    }

    def __init__(self, text: str, window):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 载入配置文件
        config = self.load_config()

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_01(self.container, config)
        self.add_widget_02(self.container, config)
        self.add_widget_03(self.container, config)
        self.add_widget_04(self.container, config)
        self.add_widget_05(self.container, config)
        self.add_widget_06(self.container, config)

        # 填充
        self.container.addStretch(1)

    # 启动自定义参数
    def add_widget_01(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("OpenAI_parameter_adjustment"))
            
        def widget_callback(widget, checked: bool):
            config = self.load_config()
            config["OpenAI_parameter_adjustment"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                "启动自定义参数", 
                "启用此功能后，将使用本页中设置的参数向模型发送请求",
                widget_init,
                widget_callback,
            )
        )

    # 启动自定义参数
    def add_widget_02(self, parent, config):
        def widget_init(widget, label):
            value = config.get("OpenAI_top_p")
            
            widget.setRange(0, 10)
            label.setText(str(value / 10))
            widget.setValue(int(value))
            
        def widget_callback(widget, label, value: int):
            config = self.load_config()
            label.setText(str(value / 10))
            config["OpenAI_top_p"] = value
            self.save_config(config)

        parent.addWidget(
            SliderCard(
                "top_p", 
                "官方默认值为 1.0",
                widget_init,
                widget_callback,
            )
        )

    # 启动自定义参数
    def add_widget_03(self, parent, config):
        def widget_init(widget, label):
            value = config.get("OpenAI_Temperature")
            
            widget.setRange(0, 10)
            label.setText(str(value / 10))
            widget.setValue(int(value))
            
        def widget_callback(widget, label, value: int):
            config = self.load_config()
            label.setText(str(value / 10))
            config["OpenAI_Temperature"] = value
            self.save_config(config)

        parent.addWidget(
            SliderCard(
                "temperature", 
                "官方默认值为 1.0",
                widget_init,
                widget_callback,
            )
        )
        
    # 启动自定义参数
    def add_widget_04(self, parent, config):
        def widget_init(widget, label):
            value = config.get("OpenAI_frequency_penalty")
            
            widget.setRange(-20, 20)
            label.setText(str(value / 10))
            widget.setValue(int(value))
            
        def widget_callback(widget, label, value: int):
            config = self.load_config()
            label.setText(str(value / 10))
            config["OpenAI_frequency_penalty"] = value
            self.save_config(config)

        parent.addWidget(
            SliderCard(
                "frequency_penalty", 
                "官方默认值为 0.0",
                widget_init,
                widget_callback,
            )
        )
        
    # 启动自定义参数
    def add_widget_05(self, parent, config):
        def widget_init(widget, label):
            value = config.get("OpenAI_frequency_penalty")
            
            widget.setRange(-20, 20)
            label.setText(str(value / 10))
            widget.setValue(int(value))
            
        def widget_callback(widget, label, value: int):
            config = self.load_config()
            label.setText(str(value / 10))
            config["OpenAI_frequency_penalty"] = value
            self.save_config(config)

        parent.addWidget(
            SliderCard(
                "frequency_penalty", 
                "官方默认值为 0.0",
                widget_init,
                widget_callback,
            )
        )
        
    # 添加连接
    def add_widget_06(self, parent, config):
        spacer = QFrame()
        spacer.setFixedHeight(8)
        
        hyper_link_label = HyperlinkLabel(QUrl("https://platform.openai.com/docs/api-reference/chat/create"), "点击查看官方文档")
        hyper_link_label.setUnderlineVisible(True)
        
        parent.addWidget(spacer, alignment = Qt.AlignHCenter)
        parent.addWidget(hyper_link_label, alignment = Qt.AlignHCenter)