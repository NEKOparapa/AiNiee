from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QVBoxLayout

from qfluentwidgets import PlainTextEdit
from qfluentwidgets import MessageBoxBase
from qfluentwidgets import SingleDirectionScrollArea

from Base.Base import Base
from Widget.GroupCard import GroupCard
from Widget.ComboBoxCard import ComboBoxCard
from Widget.LineEditCard import LineEditCard
from Widget.SwitchButtonCard import SwitchButtonCard
from Widget.EditableComboBoxCard import EditableComboBoxCard

class APIEditPage(MessageBoxBase, Base):

    def __init__(self, window, key):
        super().__init__(window)

        # 初始化
        self.key = key

        # 设置框体
        self.widget.setFixedSize(960, 720)
        self.yesButton.setText(self.tra("关闭"))
        self.cancelButton.hide()

        # 载入配置文件
        config = self.load_config()

        # 设置主布局
        self.viewLayout.setContentsMargins(0, 0, 0, 0)

        # 设置滚动器
        self.scroller = SingleDirectionScrollArea(self, orient = Qt.Vertical)
        self.scroller.setWidgetResizable(True)
        self.scroller.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.viewLayout.addWidget(self.scroller)

        # 设置滚动控件
        self.vbox_parent = QWidget(self)
        self.vbox_parent.setStyleSheet("QWidget { background: transparent; }")
        self.vbox = QVBoxLayout(self.vbox_parent)
        self.vbox.setSpacing(8)
        self.vbox.setContentsMargins(24, 24, 24, 24) # 左、上、右、下
        self.scroller.setWidget(self.vbox_parent)
        self.add_widget_name(self.vbox, config)

        # 接口地址
        if "api_url" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_url(self.vbox, config)

        # 接口地址自动补全
        if "auto_complete" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_auto_complete(self.vbox, config)

        # 接口密钥
        if "api_key" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_key(self.vbox, config)

        # 接口区域 (AWS)
        if "region" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_region(self.vbox, config)

        # Access Key (AWS)
        if "access_key" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_access_key(self.vbox, config)

        # Secret Key (AWS)
        if "secret_key" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_secret_key(self.vbox, config)

        # 接口格式
        if "api_format" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_format(self.vbox, config)

        # 模型名称
        if "model" in config.get("platforms").get(self.key).get("key_in_settings"):
            self.add_widget_model(self.vbox, config)

        # 填充
        self.vbox.addStretch(1)

    # 接口名称编辑组件
    def add_widget_name(self, parent, config):
        def init(widget):
            # 获取当前名称
            name = config.get("platforms").get(self.key).get("name", "")
            widget.set_text(name)
            widget.set_fixed_width(256)
            widget.set_placeholder_text(self.tra("请输入接口名称"))

        def text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["name"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("接口名称"),
                self.tra("自定义该接口在列表中的显示名称"),
                init = init,
                text_changed = text_changed,
            )
        )

    # 接口地址
    def add_widget_url(self, parent, config):
        def init(widget):
            widget.set_text(config.get("platforms").get(self.key).get("api_url"))
            widget.set_fixed_width(256)
            info_cont = self.tra("请输入接口地址") + " ..."
            widget.set_placeholder_text(info_cont)

        def text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["api_url"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            LineEditCard(
                self.tra("接口地址"),
                self.tra("请输入接口地址，例如 https://api.deepseek.com"),
                init = init,
                text_changed = text_changed,
            )
        )

    # 接口地址自动补全
    def add_widget_auto_complete(self, parent, config):
        def init(widget):
            widget.set_checked(config.get("platforms").get(self.key).get("auto_complete"))

        def checked_changed(widget, checked: bool):
            config = self.load_config()
            config["platforms"][self.key]["auto_complete"] = checked
            self.save_config(config)

        parent.addWidget(
            SwitchButtonCard(
                self.tra("接口地址自动补全"),
                self.tra("将自动为你填写接口地址，例如 https://api.deepseek.com -> https://api.deepseek.com/v1"),
                init = init,
                checked_changed = checked_changed,
            )
        )

    # 接口密钥
    def add_widget_key(self, parent, config):

        def text_changed(widget):
            config = self.load_config()
            config["platforms"][self.key]["api_key"] = widget.toPlainText().strip()
            self.save_config(config)

        def init(widget):
            plain_text_edit = PlainTextEdit(self)
            plain_text_edit.setPlainText(config.get("platforms").get(self.key).get("api_key"))
            plain_text_edit.setPlaceholderText(self.tra("请输入接口密钥"))
            plain_text_edit.textChanged.connect(lambda: text_changed(plain_text_edit))
            widget.addWidget(plain_text_edit)

        parent.addWidget(
            GroupCard(
                self.tra("接口密钥"),
                self.tra("请输入接口密钥，例如 sk-d0daba12345678fd8eb7b8d31c123456，多个密钥之间请使用半角逗号（,）分隔"),
                init = init,
            )
        )


     # AWS Access Key
    def add_widget_access_key(self, parent, config):

        def text_changed(widget):
            config = self.load_config()
            config["platforms"][self.key]["access_key"] = widget.toPlainText().strip()
            self.save_config(config)

        def init(widget):
            plain_text_edit = PlainTextEdit(self)
            plain_text_edit.setPlainText(config.get("platforms").get(self.key).get("access_key"))
            plain_text_edit.setPlaceholderText(self.tra("请输入AWS Access Key"))
            plain_text_edit.textChanged.connect(lambda: text_changed(plain_text_edit))
            widget.addWidget(plain_text_edit)

        parent.addWidget(
            GroupCard(
                self.tra("AWS Access Key"),
                self.tra("请输入AWS Access Key"),
                init = init,
            )
        )

     # AWS Secret Key
    def add_widget_secret_key(self, parent, config):

        def text_changed(widget):
            config = self.load_config()
            config["platforms"][self.key]["secret_key"] = widget.toPlainText().strip()
            self.save_config(config)

        def init(widget):
            plain_text_edit = PlainTextEdit(self)
            plain_text_edit.setPlainText(config.get("platforms").get(self.key).get("secret_key"))
            plain_text_edit.setPlaceholderText(self.tra("请输入AWS Secret Key"))
            plain_text_edit.textChanged.connect(lambda: text_changed(plain_text_edit))
            widget.addWidget(plain_text_edit)

        parent.addWidget(
            GroupCard(
                self.tra("AWS Secret Key"),
                self.tra("请输入AWS Secret Key"),
                init = init,
            )
        )

    # 接口区域
    def add_widget_region(self, parent, config):

        def init(widget):
            platforms = config.get("platforms").get(self.key)

            # 如果默认区域列表中不存在该条目，则添加
            items = platforms.get("region_datas", [])
            # 兼容旧配置可能没有 region_datas 的情况
            if items is None: items = []
            
            if platforms.get("region") != "" and platforms.get("region") not in items:
                items.append(platforms.get("region"))

            widget.set_items(items)
            widget.set_fixed_width(256)
            widget.set_current_index(max(0, widget.find_text(platforms.get("region"))))
            widget.set_placeholder_text(self.tra("请输入区域"))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["region"] = text.strip()
            self.save_config(config)

        def items_changed(widget, items: list[str]): 
            config = self.load_config()
            config["platforms"][self.key]["region_datas"] = items 
            self.save_config(config) 

        card = EditableComboBoxCard(
            self.tra("区域(可编辑)"),
            self.tra("请选择或者输入要使用的区域"),
            [],
            init = init,
            current_text_changed = current_text_changed,
        )
        card.items_changed.connect(lambda items: items_changed(card, items)) 
        parent.addWidget(card)


    # 接口格式
    def add_widget_format(self, parent, config):
        def init(widget):
            platform = config.get("platforms").get(self.key)

            widget.set_items(platform.get("format_datas"))
            widget.set_current_index(max(0, widget.find_text(platform.get("api_format"))))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["api_format"] = text.strip()
            self.save_config(config)

        parent.addWidget(
            ComboBoxCard(
                self.tra("接口格式"),
                self.tra("请选择接口格式，大部分模型使用 OpenAI 格式，部分中转站的 Claude 模型则使用 Anthropic 格式"),
                [],
                init = init,
                current_text_changed = current_text_changed,
            )
        )


    # 模型名称
    def add_widget_model(self, parent, config):
        def init(widget):
            platforms = config.get("platforms").get(self.key)

            # 如果默认模型列表中不存在该条目，则添加
            items = platforms.get("model_datas")
            if platforms.get("model") != "" and platforms.get("model") not in platforms.get("model_datas"):
                items.append(platforms.get("model"))

            widget.set_items(items)
            widget.set_fixed_width(256)
            widget.set_current_index(max(0, widget.find_text(platforms.get("model"))))
            widget.set_placeholder_text(self.tra("请输入模型名称"))

        def current_text_changed(widget, text: str):
            config = self.load_config()
            config["platforms"][self.key]["model"] = text.strip()
            self.save_config(config)

        def items_changed(widget, items: list[str]): 
            config = self.load_config()
            config["platforms"][self.key]["model_datas"] = items 
            self.save_config(config) 

        card = EditableComboBoxCard(
            self.tra("模型名称(可编辑)"),
            self.tra("请选择或者输入要使用的模型的名称"),
            [],
            init = init,
            current_text_changed = current_text_changed,
        )
        self.model_card = card
        card.items_changed.connect(lambda items: items_changed(card, items)) 
        
        # 从接口获取模型
        card.fetch_models_requested.connect(lambda: self._open_model_fetch_dialog())
        parent.addWidget(card)

    # 打开获取模型页面
    def _open_model_fetch_dialog(self):
        from UserInterface.Platform.ModelBrowserDialog import ModelBrowserDialog
        
        config = self.load_config()
        platform = config.get("platforms").get(self.key)
        dialog = ModelBrowserDialog(self.window(), self.key, platform)

        def _on_models_confirmed(selected_models: list[str]):
            if not selected_models:
                self.warning_toast("", self.tra("未选择任何模型"))
                return
            
            config = self.load_config()
            platforms = config.get("platforms")
            model_datas = platforms[self.key].get("model_datas", [])
            for m in selected_models:
                if m not in model_datas:
                    model_datas.append(m)
            platforms[self.key]["model_datas"] = model_datas
            
            if len(selected_models) == 1:
                platforms[self.key]["model"] = selected_models[0]
            
            self.save_config(config)
            
            try:
                items = platforms[self.key].get("model_datas", [])
                self.model_card.set_items(items)
                current_model = platforms[self.key].get("model", "")
                if current_model:
                    self.model_card.set_current_index(max(0, self.model_card.find_text(current_model)))
            except Exception as e:
                self.debug(f"refresh combobox failed: {e}")

            self.success_toast("", self.tra("已添加所选模型"))

        try:
            dialog.selectedConfirmed.connect(_on_models_confirmed)
        except Exception:
            pass

        if dialog.exec_():
            _on_models_confirmed(dialog.get_selected_models())