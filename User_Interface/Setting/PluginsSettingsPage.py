

from PyQt5.Qt import Qt
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import SingleDirectionScrollArea

from Base.Base import Base
from Widget.SwitchButtonCard import SwitchButtonCard

class PluginsSettingsPage(QFrame, Base):

    DEFAULT = {
        "plugins_enable": {},
    }

    def __init__(self, text: str, window, plugin_manager = None):
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 插件管理器
        self.plugin_manager = plugin_manager

        # 载入配置文件
        config = self.load_config()

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

        # 初始化，确保所有插件的启用状态都具有默认值
        for k, v in self.plugin_manager.get_plugins().items():
            enable = config.get("plugins_enable").get(k, None)

            if enable == None:
                config["plugins_enable"][k] = v.default_enable
            else:
                config["plugins_enable"][k] = enable

        # 更新插件启用状态
        self.save_config(config)
        self.plugin_manager.update_plugins_enable(config.get("plugins_enable"))

        # 添加控件
        for k, v in self.plugin_manager.get_plugins().items():
            def widget_init(widget):
                widget.plugin_name = k
                widget.set_checked(config.get("plugins_enable").get(k))

            def widget_callback(widget, checked: bool):
                config = self.load_config()
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