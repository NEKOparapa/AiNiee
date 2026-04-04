from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import SingleDirectionScrollArea

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Widget.SwitchButtonCard import SwitchButtonCard

class PluginsSettingsPage(QFrame, ConfigMixin, Base):

    def _build_plugins_enable(self, current_plugins_enable: dict | None) -> dict:
        current_plugins_enable = current_plugins_enable if isinstance(current_plugins_enable, dict) else {}

        return {
            plugin_name: (
                current_plugins_enable[plugin_name]
                if plugin_name in current_plugins_enable
                else plugin.default_enable
            )
            for plugin_name, plugin in self.plugin_manager.get_plugins().items()
        }

    def __init__(self, text: str, window, plugin_manager = None):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "plugins_enable": {},
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 插件管理器
        self.plugin_manager = plugin_manager

        plugins = self.plugin_manager.get_plugins()
        config["plugins_enable"] = self._build_plugins_enable(config.get("plugins_enable"))
        plugins_enable = config["plugins_enable"]

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setContentsMargins(0, 0, 0, 0)

        # 设置滚动容器
        self.scroller = SingleDirectionScrollArea(self, orient = Qt.Vertical)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.container.addWidget(self.scroller)

        # 设置容器
        self.vbox_parent = QWidget(self)
        self.vbox_parent.setStyleSheet("QWidget { background: transparent; }")
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下
        self.scroller.setWidget(self.vbox_parent)

        # 更新插件启用状态
        self.save_config(config)
        self.plugin_manager.update_plugins_enable(plugins_enable)

        # 添加控件
        for k, v in plugins.items():
            def widget_init(widget, plugin_name = k):
                widget.plugin_name = plugin_name
                widget.set_checked(plugins_enable.get(plugin_name))

            def widget_callback(widget, checked: bool):
                config = self.load_config()
                current_plugins_enable = config.get("plugins_enable")
                current_plugins_enable = current_plugins_enable if isinstance(current_plugins_enable, dict) else {}
                current_plugins_enable[widget.plugin_name] = checked
                config["plugins_enable"] = self._build_plugins_enable(current_plugins_enable)
                self.save_config(config)

                # 同步更新 plugin_manager 里的插件启用状态
                self.plugin_manager.update_plugins_enable(config["plugins_enable"])

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
