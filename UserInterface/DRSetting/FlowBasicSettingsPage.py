from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import QFrame, QWidget, QVBoxLayout
from qfluentwidgets import SingleDirectionScrollArea

from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.PlainTextEditCard import PlainTextEditCard

class FlowBasicSettingsPage(QFrame, Base):

    def __init__(self, text: str, window) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # 默认配置
        self.default = {
            "double_request_switch_settings": False,
            "request_a_platform_settings": "deepseek",
            "request_b_platform_settings": "deepseek",
            "test_original_text": "ゲオルグ\n「今度こそこの迷宮を封印し、\nイハイラも助け出すために……！",
            "test_preceding_text": "ゲオルグ\n「休憩は終わりだ。\nそろそろ出発にしよう。",
            "test_glossary": "请输入测试用术语表",
            "test_no_translate_list": "请输入测试用禁翻表",
        }

        # 载入并保存默认配置
        config = self.save_config(self.load_config_from_default())

        # 设置主容器（包含滚动区域）
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域
        self.scroll_area = SingleDirectionScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.main_layout.addWidget(self.scroll_area)

        # 创建滚动内容容器
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_area.setWidget(self.scroll_content)

        # 设置内容布局
        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setSpacing(8)
        self.content_layout.setContentsMargins(24, 24, 24, 24)

        # 添加控件到内容布局
        self.add_widget_01(self.content_layout, config)
        self.comboBoxCardA = self.add_widget_02(self.content_layout, config)
        self.comboBoxCardB = self.add_widget_03(self.content_layout, config)

        # 添加测试文本控件
        self.add_test_original_text_card(self.content_layout, config)
        self.add_test_preceding_text_card(self.content_layout, config)
        self.add_test_glossary_card(self.content_layout, config)
        self.add_test_no_translate_list_card(self.content_layout, config)

        # 添加底部弹性空间
        self.content_layout.addStretch(1)

    # 页面每次展示时触发
    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        # 页面显示时，更新两个 ComboBoxCard 的列表
        self.update_widget_02(self.comboBoxCardA)
        self.update_widget_03(self.comboBoxCardB)


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

    # 混合翻译模式
    def add_widget_01(self, parent, config):
        def widget_init(widget):
            widget.set_checked(config.get("double_request_switch_settings"))
        def widget_callback(widget, checked: bool):
            config = self.load_config()
            config["double_request_switch_settings"] = checked
            self.save_config(config)
        parent.addWidget(
            SwitchButtonCard(
                self.tra("启用双子星翻译"),
                self.tra(
                    "每个单元翻译任务，都改为流程设计中的翻译流程\n失效功能：项目设置的接口设置，AI构建术语表，AI构建禁翻表，提示词设置"
                ),
                widget_init,
                widget_callback,
            )
        )


    # 模型类型 - 接口A
    def add_widget_02(self, parent, config) -> ComboBoxCard:  # 返回 ComboBoxCard 实例

        def update_widget(widget) -> None: # widget 参数传入
            config = self.load_config()
            widget.set_items(self.get_items(config))
            widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("request_a_platform_settings")))))

        def init(widget) -> None:
            # **不再注册 show_event，初始加载在 showEvent 中统一处理**
            update_widget(widget) # 初始加载

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["request_a_platform_settings"] = self.find_tag_by_name(config, text)
            self.save_config(config)

        combobox_card_a = ComboBoxCard( # 保存实例
            self.tra("接口A"),
            self.tra("进行第一次请求所使用的接口"),
            [],
            init = init,
            current_text_changed = current_text_changed,
        )
        parent.addWidget(combobox_card_a)
        return combobox_card_a # 返回 ComboBoxCard 实例


    # 模型类型 - 接口B
    def add_widget_03(self, parent, config) -> ComboBoxCard: # 返回 ComboBoxCard 实例

        def update_widget(widget) -> None: # widget 参数传入
            config = self.load_config()
            widget.set_items(self.get_items(config))
            widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("request_b_platform_settings")))))

        def init(widget) -> None:
            # **不再注册 show_event， 初始加载在 showEvent 中统一处理**
            update_widget(widget) # 初始加载

        def current_text_changed(widget, text: str) -> None:
            config = self.load_config()
            config["request_b_platform_settings"] = self.find_tag_by_name(config, text)
            self.save_config(config)

        combobox_card_b = ComboBoxCard( # 保存实例
            self.tra("接口B"),
            self.tra("进行第二次请求所使用的接口"),
            [],
            init = init,
            current_text_changed = current_text_changed,
        )
        parent.addWidget(combobox_card_b)
        return combobox_card_b # 返回 ComboBoxCard 实例


    # 测试原文输入框
    def add_test_original_text_card(self, parent, config):
        def widget_init(widget):
            widget.set_text(config.get("test_original_text"))
        def text_changed(widget, text: str):
            config = self.load_config()
            config["test_original_text"] = text
            self.save_config(config)
        parent.addWidget(
            PlainTextEditCard(
                self.tra("测试用原文"),
                self.tra("用于验证测试效果的待翻译原文，文本占位符为 {original_text}，全局生效"),
                widget_init,
                text_changed,
                min_height=100
            )
        )

    # 上文内容输入框
    def add_test_preceding_text_card(self, parent, config):
        def widget_init(widget):
            widget.set_text(config.get("test_preceding_text"))
        def text_changed(widget, text: str):
            config = self.load_config()
            config["test_preceding_text"] = text
            self.save_config(config)
        parent.addWidget(
            PlainTextEditCard(
                self.tra("测试用上文"),
                self.tra("用于验证测试效果的的上文语境内容，文本占位符为 {previous_text}，全局生效"),
                widget_init,
                text_changed,
                min_height=100
            )
        )

    # 术语表输入框
    def add_test_glossary_card(self, parent, config):
        def widget_init(widget):
            widget.set_text(config.get("test_glossary"))
        def text_changed(widget, text: str):
            config = self.load_config()
            config["test_glossary"] = text
            self.save_config(config)
        parent.addWidget(
            PlainTextEditCard(
                self.tra("测试用术语表"),
                self.tra("用于验证测试效果的术语表，文本占位符为 {glossary}，全局生效"),
                widget_init,
                text_changed,
                min_height=100
            )
        )

    # 不翻译列表输入框
    def add_test_no_translate_list_card(self, parent, config):
        def widget_init(widget):
            widget.set_text(config.get("test_no_translate_list"))
        def text_changed(widget, text: str):
            config = self.load_config()
            config["test_no_translate_list"] = text
            self.save_config(config)
        parent.addWidget(
            PlainTextEditCard(
                self.tra("测试用禁翻表"),
                self.tra("用于验证测试效果的禁翻表，文本占位符为 {code_text}，全局生效"),
                widget_init,
                text_changed,
                min_height=100
            )
        )


    #  用于在 showEvent 中调用
    def update_widget_02(self, widget):
        def update_widget_internal(): # 创建内部函数，避免重复读取 config
            config = self.load_config()
            widget.set_items(self.get_items(config))
            widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("request_a_platform_settings")))))
        update_widget_internal() # 调用内部函数

    def update_widget_03(self, widget):
        def update_widget_internal(): # 创建内部函数，避免重复读取 config
            config = self.load_config()
            widget.set_items(self.get_items(config))
            widget.set_current_index(max(0, widget.find_text(self.find_name_by_tag(config, config.get("request_b_platform_settings")))))
        update_widget_internal() # 调用内部函数