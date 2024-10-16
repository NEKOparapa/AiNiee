
import os
import json

from rich import print
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import PillPushButton
from qfluentwidgets import SmoothScrollArea

from Widget.FlowCard import FlowCard
from Widget.SpinCard import SpinCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard

class PluginsSettingsPage(QFrame):

    DEFAULT = {
        "plugins_enable": {},
    }

    def __init__(self, text: str, parent, configurator, plugin_manager):
        super().__init__(parent = parent)

        self.setObjectName(text.replace(" ", "-"))
        self.configurator = configurator
        self.plugin_manager = plugin_manager

        # 载入配置文件
        config = self.load_config()
        config = self.save_config(config)

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)

        # 设置滚动容器
        self.scroller = SmoothScrollArea(self)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; }")
        self.container.addWidget(self.scroller)

        # 设置容器
        self.vbox_parent = QWidget()
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下
        self.scroller.setWidget(self.vbox_parent)

        # 初始化，确保所有插件的启用状态都具有默认值
        for k, v in self.plugin_manager.get_plugins().items():
            enable = config.get("plugins_enable").get(k, None)

            if enable == None:
                config["plugins_enable"][k] = v.default_enable
            else:
                config["plugins_enable"][k] = enable

        # 更新插件启用状态
        self.plugin_manager.update_plugins_enable(config.get("plugins_enable"))

        # 添加控件
        for k, v in self.plugin_manager.get_plugins().items():
            def widget_init(widget):
                widget.plugin_name = k
                widget.setChecked(config.get("plugins_enable").get(k))
                
            def widget_callback(widget, checked: bool):
                config["plugins_enable"][widget.plugin_name] = checked
                self.save_config(config)

                # 同步更新 plugin_manager 里的插件启用状态
                self.plugin_manager.update_plugins_enable(config.get("plugins_enable"))

            self.vbox.addWidget(
                SwitchButtonCard(
                    f"{v.name}", 
                    f"{v.description}",
                    widget_init,
                    widget_callback,
                )
            )

        # 填充
        self.vbox.addStretch(1)

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