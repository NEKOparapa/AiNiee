from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFileDialog, QFrame
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import FluentIcon, HorizontalSeparator

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.PushButtonCard import PushButtonCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.ComboBoxCard import ComboBoxCard

class PolishingBasicSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "polishing_target_platform": "deepseek",
            "polishing_output_path": "./output",
            "polishing_auto_set_output_path": True,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_api(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_06(self.container, config)
        self.add_widget_07(self.container, config)
        # 填充
        self.container.addStretch(1)

    # 页面每次展示时触发
    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        self.show_event(self, event) if hasattr(self, "show_event") else None

    # 获取接口列表
    def get_items(self, config) -> list:
        return [v.get("name") for k, v in config.get("platforms").items()]

    # 通过接口名字获取标签
    def find_tag_by_name(self, config, name: str) -> str:
        results = [v.get("tag") for k, v in config.get("platforms").items() if v.get("name") == name]

        if len(results) > 0:
            return results[0]
        else:
            return ""

    # 通过接口标签获取名字
    def find_name_by_tag(self, config, tag: str) -> str:
        results = [v.get("name") for k, v in config.get("platforms").items() if v.get("tag") == tag]

        if len(results) > 0:
            return results[0]
        else:
            return ""

    # 模型类型
    def add_widget_api(self, parent, config) -> None:

        def update_widget(widget) -> None:
            config = self.load_config()

            widget.set_items(self.get_items(config))
            widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("polishing_target_platform")))))

        def init(widget) -> None:
            # 注册事件，以确保配置文件被修改后，列表项目可以随之更新
            self.show_event = lambda _, event: update_widget(widget)

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["polishing_target_platform"] = self.find_tag_by_name(config, text)
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("接口平台"),
                self.tra("设置当前翻译项目所使用的接口的名称，注意，选择错误将不能进行翻译"),
                [],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 输出文件夹
    def add_widget_06(self, parent, config) -> None:
        def widget_init(widget):
            info_cont = self.tra("当前输出文件夹为") + f" {config.get("polishing_output_path")}"
            widget.set_description(info_cont)
            widget.set_text(self.tra("选择文件夹"))
            widget.set_icon(FluentIcon.FOLDER_ADD)

        def widget_callback(widget) -> None:
            # 选择文件夹
            path = QFileDialog.getExistingDirectory(None, "选择文件夹", "")
            if path == None or path == "":
                return

            # 更新UI
            info_cont = self.tra("当前输出文件夹为") + f" {path.strip()}"
            widget.set_description(info_cont)

            # 更新并保存配置
            config = self.load_config()
            config["polishing_output_path"] = path.strip()
            self.save_config(config)

        # 拖拽文件夹回调
        def drop_callback(widget, dropped_text) -> None:
            if not dropped_text:
                return

            # 更新UI
            info_cont = self.tra("当前输出文件夹为") + f" {dropped_text.strip()}"
            widget.set_description(info_cont)

            # 更新并保存配置
            config = self.load_config()
            config["polishing_output_path"] = dropped_text.strip()
            self.save_config(config)


        parent.addWidget(
            PushButtonCard(
                self.tra("输出文件夹(不能与输入文件夹相同)"),
                "",
                widget_init,
                widget_callback,
                drop_callback,
            )
        )

    # 自动设置输出文件夹开关
    def add_widget_07(self, parent, config) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("polishing_auto_set_output_path"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["polishing_auto_set_output_path"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动设置输出文件夹"),
                self.tra("启用此功能后，设置为输入文件夹的平级目录，比如输入文件夹为D:/Test/Input，输出文件夹将设置为D:/Test/AiNieeOutput"),
                widget_init,
                widget_callback,
            )
        )
