
from PyQt5.QtWidgets import QFileDialog, QFrame
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import FluentIcon, HorizontalSeparator

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.PushButtonCard import PushButtonCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.LineEditCard import LineEditCard

class OutputSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "label_output_path": "./output",
            "polishing_output_path": "./polish_output",
            "auto_set_output_path": True,
            "output_filename_suffix": "_translated", 
            "bilingual_text_order": "translation_first", 
            "response_conversion_toggle": False,
            "opencc_preset": "s2t",
            "keep_original_encoding": False,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_translation_output_path(self.container, config)
        self.add_widget_polishing_output_path(self.container, config)
        self.add_widget_auto_set(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_filename_suffix(self.container, config)
        self.add_widget_bilingual_text_order(self.container, config)
        self.add_widget_encoding(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_opencc(self.container, config)
        self.add_widget_opencc_preset(self.container, config)
        # 填充
        self.container.addStretch(1)

    # 翻译输出文件夹
    def add_widget_translation_output_path(self, parent, config) -> None:
        def widget_init(widget):
            info_cont = self.tra("当前输出文件夹为") + f" {config.get("label_output_path")}"
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
            config["label_output_path"] = path.strip()
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
            config["label_output_path"] = dropped_text.strip()
            self.save_config(config)


        parent.addWidget(
            PushButtonCard(
                self.tra("翻译输出文件夹"),
                "",
                widget_init,
                widget_callback,
                drop_callback,
            )
        )

    # 润色输出文件夹
    def add_widget_polishing_output_path(self, parent, config) -> None:
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
                self.tra("润色输出文件夹"),
                "",
                widget_init,
                widget_callback,
                drop_callback,
            )
        )

    # 自动设置输出文件夹开关
    def add_widget_auto_set(self, parent, config) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("auto_set_output_path"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_set_output_path"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动设置输出文件夹"),
                self.tra("启用此功能后，设置为输入文件夹的平级目录，比如输入文件夹为D:/Test/Input，输出文件夹将设置为D:/Test/AiNieeOutput"),
                widget_init,
                widget_callback,
            )
        )

    # 自动编码统一
    def add_widget_encoding(self, parent, config) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("keep_original_encoding"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["keep_original_encoding"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("保持输入输出文件编码一致"),
                self.tra("启用此功能后，输出译文文件的编码将保持为与输入原文文件的编码一致（若字符不兼容，仍会使用utf-8），"
                         "关闭后将始终使用 utf-8 编码（无特殊情况保持关闭即可）"),
                widget_init,
                widget_callback,
            )
        )

    # 自动简繁转换
    def add_widget_opencc(self, parent, config) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("response_conversion_toggle"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["response_conversion_toggle"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动简繁转换"),
                self.tra("启用此功能后，在翻译完成时将按照设置的字形映射规则进行简繁转换"),
                widget_init,
                widget_callback,
            )
        )

    # 简繁转换预设规则
    def add_widget_opencc_preset(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_current_index(max(0, widget.find_text(config.get("opencc_preset"))))

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["opencc_preset"] = text
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("简繁转换预设规则"),
                self.tra("进行简繁转换时的字形预设规则，常用的有：简转繁（s2t）、繁转简（t2s）"),
                [
                    "s2t",
                    "s2tw",
                    "s2hk",
                    "s2twp",
                    "t2s",
                    "t2tw",
                    "t2hk",
                    "t2jp",
                    "tw2s",
                    "tw2t",
                    "tw2sp",
                    "hk2s",
                    "hk2t",
                    "jp2t",
                ],
                init = init,
                current_text_changed = current_text_changed,
            )
        )

    # 文件名后缀设置
    def add_widget_filename_suffix(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_text(config.get("output_filename_suffix", "_translated"))
            widget.set_placeholder_text(self.tra("例如: _translated"))

        def text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["output_filename_suffix"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("文件名后缀"),
                self.tra("设置输出文件的文件名后缀，例如: _translated"),
                init=init,
                text_changed=text_changed
            )
        )

    # 双语文件文本顺序设置
    def add_widget_bilingual_text_order(self, parent, config) -> None:
        # 创建选项对列表 (显示文本, 存储值)
        order_pairs = [
            (self.tra("原文在上"), "source_first"),
            (self.tra("译文在上"), "translation_first")
        ]
        
        # 生成翻译后的选项列表
        options = [display for display, _ in order_pairs]
        
        def init(widget) -> None:
            current_value = config.get("bilingual_text_order", "original_first")
            # 查找当前值对应的索引
            index = next(
                (i for i, (_, value) in enumerate(order_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            # 查找显示文本对应的存储值
            value = next(
                (value for display, value in order_pairs if display == text),
                "original_first"  # 默认值
            )
            
            config = self.load_config()
            config["bilingual_text_order"] = value
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("双语文件文本顺序"),
                self.tra("设置双语文件中原文和译文的显示顺序，仅支持txt与epub项目"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )