
import os
import json

from rich import print
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from Widget.SpinCard import SpinCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard

class Widget_translation_settings_B3(QFrame):

    DEFAULT = {
        "reply_check_switch": {
            "Model Degradation Check": True,
            "Residual Original Text Check": True,
            "Return to Original Text Check": True,
        },
    }

    def __init__(self, text: str, parent = None, configurator = None):
        super().__init__(parent = parent)

        self.setObjectName(text.replace(" ", "-"))
        self.configurator = configurator

        # 主逻辑
        self.main()

    # 载入配置文件
    def load_config(self) -> dict[str]:
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

        # 模型退化检查
        def widget_01_init(widget):
            widget.setChecked(config.get("reply_check_switch").get("Model Degradation Check"))
            
        def widget_01_callback(widget, checked: bool):
            config["reply_check_switch"]["Model Degradation Check"] = checked
            self.save_config(config)

        self.container.addWidget(
            SwitchButtonCard(
                "模型退化检查", 
                "如在翻译结果中检查到模型退化的现象，则重试",
                widget_01_init,
                widget_01_callback,
            )
        )

        # 原文返回检查
        def widget_02_init(widget):
            widget.setChecked(config.get("reply_check_switch").get("Return to Original Text Check"))
            
        def widget_02_callback(widget, checked: bool):
            config["reply_check_switch"]["Return to Original Text Check"] = checked
            self.save_config(config)

        self.container.addWidget(
            SwitchButtonCard(
                "原文返回检查", 
                "如在翻译结果中检查到原文返回的现象，则重试",
                widget_02_init,
                widget_02_callback,
            )
        )

        # 翻译残留检查
        def widget_03_init(widget):
            widget.setChecked(config.get("reply_check_switch").get("Residual Original Text Check"))
            
        def widget_03_callback(widget, checked: bool):
            config["reply_check_switch"]["Residual Original Text Check"] = checked
            self.save_config(config)

        self.container.addWidget(
            SwitchButtonCard(
                "翻译残留检查", 
                "如在翻译结果中检查到翻译残留的现象，则重试",
                widget_03_init,
                widget_03_callback,
            )
        )

        # 填充
        self.container.addStretch(1) # 确保控件顶端对齐