from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QFrame, QLayout, QVBoxLayout, QHBoxLayout, QInputDialog
from qfluentwidgets import Action, FluentIcon, MessageBox, FluentWindow, PlainTextEdit, PushButton, ComboBox
from Base.Base import Base
from Widget.ComboBoxCard import ComboBoxCard
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilderThink import PromptBuilderThink

class SystemPromptPage(QFrame, Base):
    def __init__(self, text: str, window: FluentWindow) -> None:
        super().__init__(window)
        self.setObjectName(text.replace(" ", "-"))

        # Default configuration
        self.default = {
            "prompt_preset": PromptBuilderEnum.COMMON,
            "system_prompt_content": "",
            "custom_prompts": {}
        }

        # Load and save default config
        config = self.load_config()

        # Current custom prompt name tracker
        self.current_custom_prompt_name = None

        # Set up main container
        self.container = QVBoxLayout(self)
        self.container.setSpacing(8)
        self.container.setContentsMargins(24, 24, 24, 24)

        # Add widgets in order
        self.add_widget_header(self.container, config, window)
        self.add_custom_prompts_ui(self.container, config)
        self.add_widget_body(self.container, config, window)

        # Connect signals for custom prompt management
        self.new_button.clicked.connect(self.new_custom_prompt)
        self.delete_button.clicked.connect(self.delete_custom_prompt)
        self.custom_prompts_combo.currentTextChanged.connect(self.load_custom_prompt)
        self.plain_text_edit.textChanged.connect(self.on_text_changed)

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        if callable(getattr(self, "show_event_body", None)):
            self.show_event_body(self, event)

    def add_widget_header(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        preset_pairs = [
            (self.tra("通用"), PromptBuilderEnum.COMMON),
            (self.tra("思维链"), PromptBuilderEnum.COT),
            (self.tra("推理模型"), PromptBuilderEnum.THINK),
            (self.tra("自定义提示词"), PromptBuilderEnum.CUSTOM),
        ]
        options = [display for display, _ in preset_pairs]

        def init(widget) -> None:
            current_value = config.get("prompt_preset", self.default["prompt_preset"])
            index = next((i for i, (_, value) in enumerate(preset_pairs) if value == current_value), 0)
            widget.set_current_index(max(0, index))

        def current_text_changed(widget, text: str) -> None:
            value = next((value for display, value in preset_pairs if display == text), self.default["prompt_preset"])
            config = self.load_config()
            config["prompt_preset"] = value
            if value != PromptBuilderEnum.CUSTOM:
                if value in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT):
                    default_prompt = PromptBuilder.get_system_default(None)
                elif value == PromptBuilderEnum.THINK:
                    default_prompt = PromptBuilderThink.get_system_default(config)
                config["system_prompt_content"] = default_prompt
                self.plain_text_edit.setPlainText(default_prompt)
                self.custom_prompts_frame.setVisible(False)
            else:
                self.custom_prompts_frame.setVisible(True)
                custom_prompts = config.get("custom_prompts", {})
                self.custom_prompts_combo.clear()
                self.custom_prompts_combo.addItems(custom_prompts.keys())
                if custom_prompts:
                    # 如果有自定义提示词，选择第一个
                    first_name = next(iter(custom_prompts.keys()))
                    self.custom_prompts_combo.setCurrentText(first_name)
                    self.load_custom_prompt(first_name)
                else:
                    self.plain_text_edit.clear()
                    
            self.save_config(config)
            info_cont = self.tra("提示词预设规则切换成功") + " ..."
            self.success_toast("", info_cont)

        info_cont1 = self.tra("通用：综合通用，花费最少，兼容各种模型，完美破限")
        info_cont2 = self.tra("思维链：融入翻译三步法，提升思考深度，极大增加输出内容，极大增加消耗，提升文学质量，适合普通模型，完美破限")
        info_cont3 = self.tra("推理模型：为 DeepSeek-R1 等推理模型优化，释放推理模型的思考能力，获得最佳翻译质量")
        info_cont4 = self.tra("自定义提示词：将使用下面文本框填入的内容作为系统提示词，不支持本地接口")

        self.combo_box_card = ComboBoxCard(
            self.tra("基础提示词预设"),
            "\n".join([info_cont1, info_cont2, info_cont3, info_cont4]),
            options,
            init=init,
            current_text_changed=current_text_changed
        )
        parent.addWidget(self.combo_box_card)

    def add_custom_prompts_ui(self, parent: QLayout, config: dict) -> None:
        self.custom_prompts_frame = QFrame(self)
        self.custom_prompts_layout = QVBoxLayout(self.custom_prompts_frame)
        
        self.custom_prompts_combo = ComboBox(self)
        self.new_button = PushButton("新建", self)
        self.delete_button = PushButton("删除", self)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.custom_prompts_combo, 4)  # 给组合框更多空间
        buttons_layout.addWidget(self.new_button, 1)
        buttons_layout.addWidget(self.delete_button, 1)
        
        self.custom_prompts_layout.addLayout(buttons_layout)
        parent.addWidget(self.custom_prompts_frame)
        self.custom_prompts_frame.setVisible(config["prompt_preset"] == PromptBuilderEnum.CUSTOM)

    def add_widget_body(self, parent: QLayout, config: dict, window: FluentWindow) -> None:
        def update_widget(widget: QFrame) -> None:
            config = self.load_config()
            self.plain_text_edit.setPlainText(config.get("system_prompt_content"))

        self.plain_text_edit = PlainTextEdit(self)
        self.show_event_body = lambda _, event: update_widget(self.plain_text_edit)
        parent.addWidget(self.plain_text_edit)

    def on_text_changed(self):
        """自动保存文本变化到当前选中的自定义提示词"""
        config = self.load_config()
        current_preset = config.get("prompt_preset", self.default["prompt_preset"])
        
        if current_preset == PromptBuilderEnum.CUSTOM and self.current_custom_prompt_name:
            # 更新当前自定义提示词内容
            content = self.plain_text_edit.toPlainText().strip()
            custom_prompts = config.get("custom_prompts", {})
            custom_prompts[self.current_custom_prompt_name] = content
            config["custom_prompts"] = custom_prompts
            config["system_prompt_content"] = content
            self.save_config(config)
        else:
            # 非自定义模式直接保存
            config["system_prompt_content"] = self.plain_text_edit.toPlainText().strip()
            self.save_config(config)

    def new_custom_prompt(self):
        """新建自定义提示词 - 先弹出命名对话框"""
        name, ok = QInputDialog.getText(
            self, 
            self.tra("新建提示词"), 
            self.tra("请输入自定义提示词名称:")
        )
        
        if not ok or not name:
            return
            
        config = self.load_config()
        custom_prompts = config.get("custom_prompts", {})
        
        # 检查名称是否已存在
        if name in custom_prompts:
            msg = MessageBox(
                self.tra("名称已存在"),
                self.tra(f"提示词 '{name}' 已存在，是否覆盖?"),
                self
            )
            msg.yesButton.setText(self.tra("覆盖"))
            msg.cancelButton.setText(self.tra("取消"))
            if not msg.exec():
                return
        
        # 创建新的提示词条目
        custom_prompts[name] = ""
        config["custom_prompts"] = custom_prompts
        self.save_config(config)
        
        # 更新UI
        self.custom_prompts_combo.addItem(name)
        self.custom_prompts_combo.setCurrentText(name)
        self.current_custom_prompt_name = name
        self.plain_text_edit.clear()
        
        self.success_toast("", self.tra("已创建新的提示词模板"))

    def delete_custom_prompt(self):
        """删除当前选中的自定义提示词"""
        if not self.current_custom_prompt_name:
            return
            
        name = self.current_custom_prompt_name
        msg = MessageBox(
            self.tra("确认删除"),
            self.tra(f"确定要删除提示词 '{name}' 吗?"),
            self
        )
        msg.yesButton.setText(self.tra("删除"))
        msg.cancelButton.setText(self.tra("取消"))
        
        if msg.exec():
            config = self.load_config()
            custom_prompts = config.get("custom_prompts", {})
            
            if name in custom_prompts:
                del custom_prompts[name]
                config["custom_prompts"] = custom_prompts
                
                # 如果删除的是当前正在使用的，清除内容
                if config.get("system_prompt_content") == custom_prompts.get(name, ""):
                    config["system_prompt_content"] = ""
                    self.plain_text_edit.clear()
                
                self.save_config(config)
                
                # 更新UI
                index = self.custom_prompts_combo.findText(name)
                if index >= 0:
                    self.custom_prompts_combo.removeItem(index)
                
                # 选择下一个可用项或清空
                if self.custom_prompts_combo.count() > 0:
                    next_name = self.custom_prompts_combo.itemText(0)
                    self.custom_prompts_combo.setCurrentText(next_name)
                    self.load_custom_prompt(next_name)
                else:
                    self.current_custom_prompt_name = None
                    self.plain_text_edit.clear()
                
                self.success_toast("", self.tra("提示词已删除"))

    def load_custom_prompt(self, name):
        """加载选中的自定义提示词"""
        if name:
            config = self.load_config()
            custom_prompts = config.get("custom_prompts", {})
            
            if name in custom_prompts:
                self.current_custom_prompt_name = name
                content = custom_prompts[name]
                
                # 暂时断开自动保存连接，避免设置内容时触发保存
                try:
                    self.plain_text_edit.textChanged.disconnect(self.on_text_changed)
                    self.plain_text_edit.setPlainText(content)
                finally:
                    self.plain_text_edit.textChanged.connect(self.on_text_changed)
                
                # 更新系统提示词内容
                config["system_prompt_content"] = content
                self.save_config(config)
                
                self.success_toast("", self.tra("已加载自定义提示词"))

    def load_config(self):
        config = super().load_config()
        config.setdefault("custom_prompts", {})
        return config