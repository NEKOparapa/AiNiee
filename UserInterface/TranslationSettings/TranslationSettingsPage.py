from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFileDialog, QFrame, QLabel, QLayout, QStackedWidget
from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import FluentIcon, FluentWindow, HorizontalSeparator, PillPushButton, SegmentedWidget

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.PushButtonCard import PushButtonCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SpinCard import SpinCard
from Widget.FlowCard import FlowCard




class TranslationSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))


        self.pivot = SegmentedWidget(self)  # 创建一个 SegmentedWidget 实例，分段式导航栏
        self.stackedWidget = QStackedWidget(self)  # 创建一个 QStackedWidget 实例，堆叠式窗口
        self.vBoxLayout = QVBoxLayout(self)  # 创建一个垂直布局管理器

        self.A_settings = TranslationBasicSettingsPage('A_settings', window)  # 创建实例，指向界面
        self.B_settings = TranslationAdvanceSettingsPage('B_settings', window)  # 创建实例，指向界面

        info_cont1 = self.tra("基础设置")
        info_cont2 = self.tra("高级设置")

        # 添加子界面到分段式导航栏
        self.addSubInterface(self.A_settings, 'A_settings', info_cont1)
        self.addSubInterface(self.B_settings, 'B_settings', info_cont2)

        # 将分段式导航栏和堆叠式窗口添加到垂直布局中
        self.vBoxLayout.addWidget(self.pivot)
        self.vBoxLayout.addWidget(self.stackedWidget)
        self.vBoxLayout.setContentsMargins(5, 5, 5, 0)  # 分别设置左、上、右、下的边距

        # 连接堆叠式窗口的 currentChanged 信号到槽函数 onCurrentIndexChanged
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.stackedWidget.setCurrentWidget(self.A_settings)  # 设置默认显示的子界面为xxx界面
        self.pivot.setCurrentItem(self.A_settings.objectName())  # 设置分段式导航栏的当前项为xxx界面

    def addSubInterface(self, widget: QLabel, objectName, text):
        """
        添加子界面到堆叠式窗口和分段式导航栏
        """
        widget.setObjectName(objectName)
        #widget.setAlignment(Qt.AlignCenter) # 设置 widget 对象的文本（如果是文本控件）在控件中的水平对齐方式
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget),
        )

    def onCurrentIndexChanged(self, index):
        """
        槽函数：堆叠式窗口的 currentChanged 信号的槽函数
        """
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())



class TranslationBasicSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "pre_line_counts": 0,
            "source_language": "auto",
            "target_language": "chinese_simplified",
            "label_output_path": "./output",
            "auto_set_output_path": True,
            "keep_original_encoding": False,
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件

        self.add_widget_source_language(self.container, config)
        self.add_widget_target_language(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_pre_lines(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_output_path(self.container, config)
        self.add_widget_auto_set(self.container, config)
        self.container.addWidget(HorizontalSeparator())
        self.add_widget_encoding(self.container, config)
        # 填充
        self.container.addStretch(1)


    # 参考上文行数
    def add_widget_pre_lines(self, parent, config) -> None:
        def init(widget) -> None:
            widget.set_range(0, 9999999)
            widget.set_value(config.get("pre_line_counts"))

        def value_changed(widget, value: int) -> None:
            config = self.load_config()
            config["pre_line_counts"] = value
            self.save_config(config)

        parent.addWidget(
            SpinCard(
                self.tra("参考上文行数"),
                self.tra("行数不宜设置过大，建议10行以内 (不支持本地类接口)"),
                init = init,
                value_changed = value_changed,
            )
        )

    # 原文语言
    def add_widget_source_language(self, parent, config) -> None:
        # 定义语言与值的配对列表（显示文本, 存储值）
        source_language_pairs = [
            (self.tra("自动检测"), "auto"),
            (self.tra("日语"), "japanese"),
            (self.tra("英语"), "english"),
            (self.tra("韩语"), "korean"),
            (self.tra("俄语"), "russian"),
            (self.tra("德语"), "german"),
            (self.tra("法语"), "french"),
            (self.tra("简中"), "chinese_simplified"),
            (self.tra("繁中"), "chinese_traditional"),
            (self.tra("西班牙语"), "spanish"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in source_language_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("source_language", "auto")

            # 通过值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时存储对应的值"""
            # 通过显示文本查找对应的值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "auto"  # 默认值
            )
            
            config = self.load_config()
            config["source_language"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, _ in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("原文语言"),
                self.tra("设置当前翻译项目所使用的原始文本的语言，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    # 译文语言
    def add_widget_target_language(self, parent, config) -> None:
        # 定义语言与值的配对列表（显示文本, 存储值）
        target_language_pairs = [
            (self.tra("简中"), "chinese_simplified"),
            (self.tra("繁中"), "chinese_traditional"),
            (self.tra("英语"), "english"),
            (self.tra("日语"), "japanese"),
            (self.tra("韩语"), "korean"),
            (self.tra("俄语"), "russian"),
            (self.tra("德语"), "german"),
            (self.tra("法语"), "french"),
            (self.tra("西班牙语"), "spanish"),
        ]

        # 生成翻译后的配对列表
        translated_pairs = [(self.tra(display), value) for display, value in target_language_pairs]

        def init(widget) -> None:
            """初始化时根据存储的值设置当前选项"""
            current_config = self.load_config()
            current_value = current_config.get("target_language", "chinese_simplified")

            # 通过值查找对应的索引
            index = next(
                (i for i, (_, value) in enumerate(translated_pairs) if value == current_value),
                0  # 默认选择第一个选项
            )
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            """选项变化时存储对应的值"""
            # 通过显示文本查找对应的值
            value = next(
                (value for display, value in translated_pairs if display == text),
                "chinese_simplified"  # 默认值
            )
            
            config = self.load_config()
            config["target_language"] = value
            self.save_config(config)

        # 创建选项列表（使用翻译后的显示文本）
        options = [display for display, _ in translated_pairs]

        parent.addWidget(
            ComboBoxCard(
                self.tra("译文语言"),
                self.tra("设置当前翻译项目所期望的译文文本的语言，注意，选择错误将不能进行翻译"),
                options,
                init=init,
                current_text_changed=current_text_changed
            )
        )

    # 输出文件夹
    def add_widget_output_path(self, parent, config) -> None:
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
                self.tra("输出文件夹(不能与输入文件夹相同)"),
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



class TranslationAdvanceSettingsPage(QFrame, Base):

    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "few_shot_and_example_switch": True,
            "auto_process_text_code_segment": False,
            "response_conversion_toggle": False,
            "opencc_preset": "s2t",
            "response_check_switch": {
                "return_to_original_text_check": True,
                "residual_original_text_check": True,
                "newline_character_count_check": True,
            },
        }

        # 载入用户配置合并类默认配置，并重新保存配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器
        self.vbox = QVBoxLayout(self)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下

        # 添加控件
        self.add_widget_few_shot_and_example(self.vbox, config, window)
        self.vbox.addWidget(HorizontalSeparator())
        self.add_auto_process_text_code_segment(self.vbox, config, window)
        self.vbox.addWidget(HorizontalSeparator())
        self.add_widget_opencc(self.vbox, config, window)
        self.add_widget_opencc_preset(self.vbox, config, window)
        self.vbox.addWidget(HorizontalSeparator())
        self.add_widget_result_check(self.vbox, config, window)

        # 填充
        self.vbox.addStretch(1)

    # 示例模块和预回复模块开关
    def add_widget_few_shot_and_example(self, parent: QLayout, config: dict, window: FluentWindow) -> None:

        def init(widget: SwitchButtonCard) -> None:
            widget.set_checked(config.get("few_shot_and_example_switch"))

        def checked_changed(widget: SwitchButtonCard, checked: bool) -> None:
            config = self.load_config()
            config["few_shot_and_example_switch"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("动态示例和预回复功能"),
                self.tra("启用此功能后，将在构建整体的翻译提示词时，自动生成动态Few-shot和构建模型预回复内容，不支持本地接口"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 自动预处理
    def add_auto_process_text_code_segment(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def widget_init(widget) -> None:
            widget.set_checked(config.get("auto_process_text_code_segment"))

        def widget_callback(widget, checked: bool) -> None:
            config = self.load_config()
            config["auto_process_text_code_segment"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("自动预处理文本"),
                self.tra(
                "启用此功能后，根据正则库与禁翻表，将在翻译前移除文本首尾的非翻译内容，占位文本中间的非翻译内容，并在翻译后还原"
                ),
                widget_init,
                widget_callback,
            )
        )

    # 自动简繁转换
    def add_widget_opencc(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
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
    def add_widget_opencc_preset(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
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

    # 结果检查
    def add_widget_result_check(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def on_toggled(checked: bool, key) -> None:
            config = self.load_config()
            config["response_check_switch"][key] = checked
            self.save_config(config)

        def widget_init(widget) -> None:

            info_cont1 = self.tra("原文返回检查")
            info_cont2 = self.tra("翻译残留检查")
            info_cont3 = self.tra("换行符数检查")

            pairs = [
                (info_cont1, "return_to_original_text_check"),
                (info_cont2, "residual_original_text_check"),
                (info_cont3, "newline_character_count_check"),
            ]

            for v in pairs:
                pill_push_button = PillPushButton(v[0])
                pill_push_button.setContentsMargins(4, 0, 4, 0) # 左、上、右、下
                pill_push_button.setChecked(config["response_check_switch"].get(v[1]))
                pill_push_button.toggled.connect(lambda checked, key = v[1]: on_toggled(checked, key))
                widget.add_widget(pill_push_button)

        parent.addWidget(
            FlowCard(
                self.tra("翻译结果检查"),
                self.tra("将在翻译结果中检查激活的规则（点亮按钮为激活）：如检测到对应情况，则视为任务执行失败"),
                widget_init
            )
        )