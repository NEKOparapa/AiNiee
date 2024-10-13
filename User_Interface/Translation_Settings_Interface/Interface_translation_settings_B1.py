
import os
import json

from rich import print
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from Widget.SpinCard import SpinCard
from Widget.ComboBoxCard import ComboBoxCard

class Widget_translation_settings_B1(QFrame):

    DEFAULT = {
        "lines_limit_switch": True,
        "tokens_limit_switch": False,
        "lines_limit": 16,
        "tokens_limit": 512,
        "pre_line_counts": 0,
        "user_thread_counts": 0,
        "retry_count_limit": 1,
        "round_limit": 8,
    }

    def __init__(self, text: str, parent = None, configurator = None):
        super().__init__(parent = parent)

        self.setObjectName(text.replace(" ", "-"))
        self.configurator = configurator

        # 主逻辑
        self.main()

    # 载入配置文件
    def load_config(self) -> dict:
        config = {}

        if os.path.exists(os.path.join(self.configurator.resource_dir, "config.json")):
            with open(os.path.join(self.configurator.resource_dir, "config.json"), "r", encoding = "utf-8") as reader:
                config = json.load(reader)

        return config

    # 保存配置文件
    def save_config(self, new: dict) -> None:
        path = os.path.join(self.configurator.resource_dir, "config.json")
        
        # 读取配置文件
        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                old = json.load(reader)
        else:
            old = {}

        # 修改配置文件中的条目：如果条目存在，这更新值，如果不存在，则设置默认值
        for k, v in self.DEFAULT.items():
            if not k in new.keys():
                old[k] = v
            else:
                old[k] = new[k]

        # 写入配置文件
        with open(path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(old, indent = 4, ensure_ascii = False))

        return old
    
    def main(self):
        # 载入配置文件
        config = self.load_config()
        config = self.save_config(config)

        # 设置容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 任务切分模式
        def widget_01_init(widget):
            lines_limit_switch = config.get("lines_limit_switch")
            tokens_limit_switch = config.get("tokens_limit_switch")

            if lines_limit_switch == True and tokens_limit_switch == False:
                widget.setCurrentIndex(0)
                
            if lines_limit_switch == False and tokens_limit_switch == True:
                widget.setCurrentIndex(1)
            
        def widget_01_callback(widget, index: int):
            if index == 0:
                config["lines_limit_switch"] = True
                config["tokens_limit_switch"] = False
                
            if index == 1:
                config["lines_limit_switch"] = False
                config["tokens_limit_switch"] = True
                
            self.save_config(config)

        self.container.addWidget(
            ComboBoxCard(
                "任务切分模式", 
                "选择翻译任务切分的模式",
                [
                    "行数模式",
                    "Token 模式",
                ],
                widget_01_init,
                widget_01_callback,
            )
        )

        # 每次发送的最大行数
        def widget_02_init(widget):
            widget.setRange(0, 2048)
            widget.setValue(config.get("lines_limit"))

        def widget_02_callback(widget, value: int):
            config["lines_limit"] = value
            self.save_config(config)

        self.container.addWidget(
            SpinCard(
                "每次发送的最大行数", 
                "当任务切分模式设置为 行数模式 时生效",
                widget_02_init,
                widget_02_callback,
            )
        )

        # 每次发送的最大 Token 数
        def widget_03_init(widget):
            widget.setRange(0, 2048)
            widget.setValue(config.get("tokens_limit"))

        def widget_03_callback(widget, value: int):
            config["tokens_limit"] = value
            self.save_config(config)
            
        self.container.addWidget(
            SpinCard(
                "每次发送的最大 Token 数", 
                "当任务切分模式设置为 Token 模式 时生效",
                widget_03_init,
                widget_03_callback,
            )
        )
        
        # 参考上文行数
        def widget_04_init(widget):
            widget.setRange(0, 2048)
            widget.setValue(config.get("pre_line_counts"))

        def widget_04_callback(widget, value: int):
            config["pre_line_counts"] = value
            self.save_config(config)
            
        self.container.addWidget(
            SpinCard(
                "参考上文行数", 
                "每个任务携带的参考上文的行数（不支持 Sakura v0.9 模型）",
                widget_04_init,
                widget_04_callback,
            )
        )

        # 并行子任务数量
        def widget_05_init(widget):
            widget.setRange(0, 2048)
            widget.setValue(config.get("user_thread_counts"))

        def widget_05_callback(widget, value: int):
            config["user_thread_counts"] = value
            self.save_config(config)
            
        self.container.addWidget(
            SpinCard(
                "并行子任务数量", 
                "合理设置可以极大的增加翻译速度，请设置为本地模型的 np 值或者参考在线接口的官方文档，设置为 0 为自动模式",
                widget_05_init,
                widget_05_callback,
            )
        )
        
        # 错误重试的最大次数
        def widget_06_init(widget):
            widget.setRange(0, 2048)
            widget.setValue(config.get("retry_count_limit"))

        def widget_06_callback(widget, value: int):
            config["retry_count_limit"] = value
            self.save_config(config)
            
        self.container.addWidget(
            SpinCard(
                "错误重试的最大次数", 
                "当遇到行数不匹配等翻译错误时进行重试的最大次数",
                widget_06_init,
                widget_06_callback,
            )
        )

        # 翻译流程的最大轮次
        def widget_07_init(widget):
            widget.setRange(1, 2048)
            widget.setValue(config.get("round_limit"))

        def widget_07_callback(widget, value: int):
            config["round_limit"] = value
            self.save_config(config)
            
        self.container.addWidget(
            SpinCard(
                "翻译流程的最大轮次", 
                "当完成一轮翻译后，如果还有未翻译的条目，将重新开始新的翻译流程，直到翻译完成或者达到最大轮次",
                widget_07_init,
                widget_07_callback,
            )
        )

        # 填充
        self.container.addStretch(1) # 确保控件顶端对齐