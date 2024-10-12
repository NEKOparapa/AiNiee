
import os
import json

from rich import print
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout

from Widget.SpinCard import SpinCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard

class Widget_translation_settings_B2(QFrame):

    DEFAULT = {
        "cot_toggle": False,
        "cn_prompt_toggle": False,
        "preserve_line_breaks_toggle": False,
        "text_clear_toggle": False,
        "response_conversion_toggle": False,
        "opencc_preset": "s2t",
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
    def save_config(self, config: dict) -> None:
        config = self.fill_config(config)
        with open(os.path.join(self.configurator.resource_dir, "config.json"), "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(config, indent = 4, ensure_ascii = False))

    # 填充配置文件缺失的条目
    def fill_config(self, config: dict) -> dict:
        if os.path.exists(os.path.join(self.configurator.resource_dir, "config.json")):
            with open(os.path.join(self.configurator.resource_dir, "config.json"), "r", encoding = "utf-8") as reader:
                exists = json.load(reader)
                for k, v in exists.items():
                    if not k in config.keys():
                        config[k] = v
                
        for k, v in self.DEFAULT.items():
            if not k in config.keys():
                config[k] = v

        return config
    
    def main(self):
        # 载入配置文件
        config = self.load_config()
        self.save_config(config)

        # 设置容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 思维链模式
        def widget_01_init(widget):
            widget.setChecked(config.get("cot_toggle"))
            
        def widget_01_callback(widget, checked: bool):
            config["cot_toggle"] = checked
            self.save_config(config)

        self.container.addWidget(
            SwitchButtonCard(
                "思维链模式", 
                "思维链（CoT）模式是一种高级翻译指令模式，在逻辑能力强的模型上可以取得更好的翻译效果，注意，会消耗更多 Token",
                widget_01_init,
                widget_01_callback,
            )
        )
        
        # 中文提示词
        def widget_02_init(widget):
            widget.setChecked(config.get("cn_prompt_toggle"))
            
        def widget_02_callback(widget, checked: bool):
            config["cn_prompt_toggle"] = checked
            self.save_config(config)

        self.container.addWidget(
            SwitchButtonCard(
                "中文提示词", 
                "默认使用英文提示词，启用此功能后将使用中文提示词（Sakura 模型固定为中文提示词，无需启用此功能）",
                widget_02_init,
                widget_02_callback,
            )
        )

        # 保留句内换行符
        def widget_03_init(widget):
            widget.setChecked(config.get("preserve_line_breaks_toggle"))
            
        def widget_03_callback(widget, checked: bool):
            config["preserve_line_breaks_toggle"] = checked
            self.save_config(config)

        self.container.addWidget(
            SwitchButtonCard(
                "保留句内换行符", 
                "启用此功能后将尝试保留每个句子内的换行符",
                widget_03_init,
                widget_03_callback,
            )
        )

        # 保留首尾非文本字符
        def widget_04_init(widget):
            widget.setChecked(config.get("text_clear_toggle"))
            
        def widget_04_callback(widget, checked: bool):
            config["text_clear_toggle"] = checked
            self.save_config(config)

        self.container.addWidget(
            SwitchButtonCard(
                "保留首尾非文本字符", 
                "启用此功能后将尝试保留每个句子首尾的非文本字符",
                widget_04_init,
                widget_04_callback,
            )
        )
        
        # 自动转换为繁体中文
        def widget_05_init(widget):
            widget.setChecked(config.get("response_conversion_toggle"))
            
        def widget_05_callback(widget, checked: bool):
            config["response_conversion_toggle"] = checked
            self.save_config(config)

        self.container.addWidget(
            SwitchButtonCard(
                "自动转换为繁体中文", 
                "启用此功能将在翻译完成后自动将译文转换为繁体中文",
                widget_05_init,
                widget_05_callback,
            )
        )
        
        # 简繁转换字体映射规则
        def widget_06_init(widget):
            widget.setCurrentIndex(max(0, widget.findText(config.get("opencc_preset"))))

        def widget_06_callback(widget, index: int):
            config["opencc_preset"] = widget.currentText()
            self.save_config(config)

        self.container.addWidget(
            ComboBoxCard(
                "简繁转换字形映射规则", 
                "进行简繁转换时的字形映射规则",
                    [
                        "s2t",
                        "s2tw",
                        "s2hk",
                        "s2twp",
                    ],
                widget_06_init,
                widget_06_callback,
            )
        )

        # 填充
        self.container.addStretch(1) # 确保控件顶端对齐