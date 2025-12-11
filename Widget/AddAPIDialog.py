from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame

from qfluentwidgets import (
    MessageBoxBase, LineEdit, StrongBodyLabel, CaptionLabel,
    ComboBox, SwitchButton, FlowLayout, PillPushButton,SingleDirectionScrollArea, EditableComboBox,
    PlainTextEdit
)

# Fix Bug: 修复 qfluentwidgets 滚动条事件处理崩溃问题 ---
try:
    from qfluentwidgets.components.widgets.scroll_bar import SmoothScrollDelegate
    
    # 保存原始方法
    _original_eventFilter = SmoothScrollDelegate.eventFilter

    def _safe_eventFilter(self, obj, e):
        try:
            return _original_eventFilter(self, obj, e)
        except AttributeError:
            # 如果捕获到 'QWheelEvent' 没有 'size' 属性的错误，直接忽略该事件
            return False
        except Exception:
            # 捕获其他可能的异常以防万一
            return False

    # 替换为安全的方法
    SmoothScrollDelegate.eventFilter = _safe_eventFilter
except ImportError:
    pass # 如果版本不同找不到该类，则跳过修复


from Base.Base import Base

class AddAPIDialog(MessageBoxBase, Base):
    """添加新接口的简易对话框"""
    
    def __init__(self, window, preset_platforms: dict, on_confirm=None):
        super().__init__(window)
        
        self.preset_platforms = preset_platforms
        self.on_confirm = on_confirm
        self.selected_platform_tag = None
        
        # 设置对话框大小
        self.widget.setMinimumSize(680, 750)
        self.yesButton.setText(self.tra("确认"))
        self.cancelButton.setText(self.tra("取消"))
        
        self._build_ui()
        
    def _build_ui(self):
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        self.viewLayout.setSpacing(12)
        
        # 标题
        title = StrongBodyLabel(self.tra("添加新接口"))
        title.setStyleSheet("font-size: 18px;")
        self.viewLayout.addWidget(title)
        
        # 滚动区域
        self.scroll_area = SingleDirectionScrollArea(orient=Qt.Vertical)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("QWidget { background: transparent; }")
        self.scroll_layout = QVBoxLayout(scroll_widget)
        self.scroll_layout.setContentsMargins(0, 8, 12, 8)
        self.scroll_layout.setSpacing(12)
        self.scroll_area.setWidget(scroll_widget)
        self.viewLayout.addWidget(self.scroll_area)
        
        # 接口名称
        self.name_label = self._add_section_label(self.tra("接口名称"))
        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText(self.tra("请输入接口名称，例如：我的GPT接口"))
        self.name_edit.setClearButtonEnabled(True)
        self.scroll_layout.addWidget(self.name_edit)
        
        # 接口平台选择
        self._add_section_label(self.tra("接口平台"))
        
        # 初始化平台按钮
        self.platform_buttons = {}
        self._init_platform_buttons()
        
        # 接口地址
        self.url_label = self._add_section_label(self.tra("接口地址"))
        self.url_edit = LineEdit()
        self.url_edit.setPlaceholderText(self.tra("请输入接口地址，例如：https://api.openai.com/v1"))
        self.url_edit.setClearButtonEnabled(True)
        self.scroll_layout.addWidget(self.url_edit)
        
        # API Key
        self.api_key_label = self._add_section_label(self.tra("接口密钥"))
        self.api_key_edit = PlainTextEdit()
        self.api_key_edit.setPlaceholderText(self.tra("请输入接口密钥，例如：sk-xxxxxxxx，多个密钥之间请使用半角逗号（,）分隔"))
        self.api_key_edit.setFixedHeight(80)
        self.scroll_layout.addWidget(self.api_key_edit)

        # 区域 (Amazon Bedrock 专用字段)
        self.region_label = self._add_section_label(self.tra("区域"))
        self.region_edit = LineEdit()
        self.region_edit.setPlaceholderText(self.tra("请输入区域，例如：us-east-1"))
        self.scroll_layout.addWidget(self.region_edit)

        # Access Key (Amazon Bedrock 专用字段)
        self.access_key_label = self._add_section_label(self.tra("AWS Access Key"))
        self.access_key_edit = LineEdit()
        self.access_key_edit.setPlaceholderText(self.tra("请输入 AWS Access Key ID"))
        self.scroll_layout.addWidget(self.access_key_edit)

        # Secret Key (Amazon Bedrock 专用字段)
        self.secret_key_label = self._add_section_label(self.tra("AWS Secret Key"))
        self.secret_key_edit = LineEdit()
        self.secret_key_edit.setPlaceholderText(self.tra("请输入 AWS Secret Access Key"))
        self.scroll_layout.addWidget(self.secret_key_edit)
        
        # 模型名称
        self.model_label = self._add_section_label(self.tra("模型名称"))
        self.model_combo = EditableComboBox()
        self.model_combo.setPlaceholderText(self.tra("请输入或选择模型名称"))
        self.scroll_layout.addWidget(self.model_combo)
        
        # 自定义选项容器（仅自定义平台显示）
        self.custom_options_container = QFrame()
        custom_options_layout = QVBoxLayout(self.custom_options_container)
        custom_options_layout.setContentsMargins(0, 0, 0, 0)
        custom_options_layout.setSpacing(12)
        
        # 接口格式
        format_label = StrongBodyLabel(self.tra("接口格式"))
        custom_options_layout.addWidget(format_label)
        
        self.format_combo = ComboBox()
        self.format_combo.addItems(["OpenAI", "Anthropic", "Google"])
        custom_options_layout.addWidget(self.format_combo)
        
        # 接口地址自动补全
        auto_complete_row = QHBoxLayout()
        auto_complete_label = StrongBodyLabel(self.tra("接口地址自动补全"))
        self.auto_complete_switch = SwitchButton()
        self.auto_complete_switch.setChecked(True)
        auto_complete_row.addWidget(auto_complete_label)
        auto_complete_row.addStretch()
        auto_complete_row.addWidget(self.auto_complete_switch)
        custom_options_layout.addLayout(auto_complete_row)
        
        auto_complete_desc = CaptionLabel(self.tra("自动为接口地址添加 /v1 后缀"))
        auto_complete_desc.setStyleSheet("color: #888;")
        custom_options_layout.addWidget(auto_complete_desc)
        
        self.scroll_layout.addWidget(self.custom_options_container)
        self.custom_options_container.setVisible(False)
        
        # 初始隐藏 Bedrock 字段
        self._set_bedrock_fields_visible(False)

        # 填充
        self.scroll_layout.addStretch()
        
    def _add_section_label(self, text: str):
        label = StrongBodyLabel(text)
        self.scroll_layout.addWidget(label)
        return label
        
    def _add_description_label(self, text: str):
        label = CaptionLabel(text)
        label.setStyleSheet("color: #888;")
        self.scroll_layout.addWidget(label)

    def _set_bedrock_fields_visible(self, visible: bool):
        """控制 Amazon Bedrock 专用字段的显隐"""
        self.region_label.setVisible(visible)
        self.region_edit.setVisible(visible)
        self.access_key_label.setVisible(visible)
        self.access_key_edit.setVisible(visible)
        self.secret_key_label.setVisible(visible)
        self.secret_key_edit.setVisible(visible)

    def _init_platform_buttons(self):
        """初始化平台选择按钮"""
        
        local_platforms = {k: v for k, v in self.preset_platforms.items() 
                         if v.get("group") == "local"}
        
        online_platforms = {k: v for k, v in self.preset_platforms.items() 
                          if v.get("group") == "online" and k != "amazonbedrock"}
        
        other_platforms = {}
        # 将 amazonbedrock 和 custom 归类到其他
        if "amazonbedrock" in self.preset_platforms:
             other_platforms["amazonbedrock"] = self.preset_platforms["amazonbedrock"]
        
        if "custom" in self.preset_platforms:
             other_platforms["custom"] = self.preset_platforms["custom"]

        # 第一行：本地模型
        if local_platforms:
            local_label = CaptionLabel(self.tra("本地模型"))
            local_label.setStyleSheet("color: #666; margin-top: 4px; font-weight: 500;")
            self.scroll_layout.addWidget(local_label)
            
            local_container = QFrame()
            local_layout = FlowLayout(local_container, needAni=False)
            local_layout.setContentsMargins(0, 4, 0, 8)
            local_layout.setHorizontalSpacing(8)
            local_layout.setVerticalSpacing(8)
            
            for tag, platform in local_platforms.items():
                btn = PillPushButton(platform.get("name", tag))
                btn.setCheckable(True)
                btn.setMinimumWidth(80)
                btn.clicked.connect(lambda checked, t=tag: self._on_platform_selected(t))
                self.platform_buttons[tag] = btn
                local_layout.addWidget(btn)
            
            self.scroll_layout.addWidget(local_container)
        
        # 第二行：官方接口
        if online_platforms:
            online_label = CaptionLabel(self.tra("官方接口"))
            online_label.setStyleSheet("color: #666; margin-top: 4px; font-weight: 500;")
            self.scroll_layout.addWidget(online_label)
            
            online_container = QFrame()
            online_layout = FlowLayout(online_container, needAni=False)
            online_layout.setContentsMargins(0, 4, 0, 8)
            online_layout.setHorizontalSpacing(8)
            online_layout.setVerticalSpacing(8)
            
            for tag, platform in online_platforms.items():
                btn = PillPushButton(platform.get("name", tag))
                btn.setCheckable(True)
                btn.setMinimumWidth(80)
                btn.clicked.connect(lambda checked, t=tag: self._on_platform_selected(t))
                self.platform_buttons[tag] = btn
                online_layout.addWidget(btn)
            
            self.scroll_layout.addWidget(online_container)
        
        # 第三行：其他 (包含自定义)
        if other_platforms:
            others_label = CaptionLabel(self.tra("其他"))
            others_label.setStyleSheet("color: #666; margin-top: 4px; font-weight: 500;")
            self.scroll_layout.addWidget(others_label)
            
            others_container = QFrame()
            others_layout = FlowLayout(others_container, needAni=False)
            others_layout.setContentsMargins(0, 4, 0, 8)
            others_layout.setHorizontalSpacing(8)
            others_layout.setVerticalSpacing(8)
            
            for tag, platform in other_platforms.items():
                btn = PillPushButton(platform.get("name", tag))
                btn.setCheckable(True)
                btn.setMinimumWidth(80)
                btn.clicked.connect(lambda checked, t=tag: self._on_platform_selected(t))
                self.platform_buttons[tag] = btn
                others_layout.addWidget(btn)
            
            self.scroll_layout.addWidget(others_container)
        
    def _on_platform_selected(self, tag: str):
        """处理平台选择，根据配置文件填充默认数据"""
        # 单选逻辑
        for t, btn in self.platform_buttons.items():
            btn.setChecked(t == tag)
        
        self.selected_platform_tag = tag
        
        # 获取平台预设数据
        platform = self.preset_platforms.get(tag, {})
        group = platform.get("group", "")
        
        # 1. 自动填充模型列表
        model_datas = platform.get("model_datas", [])
        self.model_combo.clear()
        self.model_combo.addItems(model_datas)
        if model_datas:
            # 尝试选择默认模型
            default_model = platform.get("model", model_datas[0])
            idx = self.model_combo.findText(default_model)
            self.model_combo.setCurrentIndex(max(0, idx))

        # 2. 自动填充接口格式 (Custom需要)
        format_datas = platform.get("format_datas", ["OpenAI", "Anthropic", "Google"])
        default_format = platform.get("api_format", "OpenAI")
        self.format_combo.clear()
        self.format_combo.addItems(format_datas)
        self.format_combo.setCurrentIndex(max(0, self.format_combo.findText(default_format)))
        
        # 3. 自动补全开关默认值
        auto_complete_default = platform.get("auto_complete", True)
        self.auto_complete_switch.setChecked(auto_complete_default)

        # ---------------- 显隐核心逻辑 ----------------
        
        # 1. Amazon Bedrock：隐藏 URL/Key，显示 AWS
        if tag == "amazonbedrock":
            self.url_label.setVisible(False)
            self.url_edit.setVisible(False)
            self.api_key_label.setVisible(False)
            self.api_key_edit.setVisible(False)
            
            self._set_bedrock_fields_visible(True)
            self.custom_options_container.setVisible(False)
            
            # 预填 Region
            self.region_edit.setText(platform.get("region", ""))
            self.access_key_edit.clear()
            self.secret_key_edit.clear()

        # 2. 自定义 (Custom)：全部显示
        elif tag == "custom":
            self.url_label.setVisible(True)
            self.url_edit.setVisible(True)
            self.url_edit.setEnabled(True)
            # 预填（通常为空）
            self.url_edit.setText(platform.get("api_url", ""))
            self.url_edit.setPlaceholderText(self.tra("请输入接口地址"))
            
            self.api_key_label.setVisible(True)
            self.api_key_edit.setVisible(True)
            # 预填（通常为空）
            self.api_key_edit.setPlainText(platform.get("api_key", ""))
            
            self._set_bedrock_fields_visible(False)
            self.custom_options_container.setVisible(True)

        # 3. 本地模型 (Local)：显示 URL，隐藏 Key
        elif group == "local":
            self.url_label.setVisible(True)
            self.url_edit.setVisible(True)
            self.url_edit.setEnabled(True) # 本地地址允许修改 (如端口)
            # 预填默认本地地址
            self.url_edit.setText(platform.get("api_url", ""))
            self.url_edit.setPlaceholderText(self.tra("请输入接口地址"))
            
            self.api_key_label.setVisible(False) # 隐藏 Key
            self.api_key_edit.setVisible(False)
            
            self._set_bedrock_fields_visible(False)
            self.custom_options_container.setVisible(False)

        # 4. 官方接口 (Online)：隐藏 URL (固定)，显示 Key
        else:
            self.url_label.setVisible(False) # 隐藏地址
            self.url_edit.setVisible(False)
            # 填入预设 URL (虽然隐藏但保存时需要)
            self.url_edit.setText(platform.get("api_url", ""))
            
            self.api_key_label.setVisible(True)
            self.api_key_edit.setVisible(True)
            # 预填 Key (通常为空，等待用户输入)
            self.api_key_edit.setPlainText(platform.get("api_key", ""))
            
            self._set_bedrock_fields_visible(False)
            self.custom_options_container.setVisible(False)
            
    def accept(self):
        """确认添加"""
        name = self.name_edit.text().strip()
        if not name:
            self.warning_toast("", self.tra("请输入接口名称"))
            return
            
        if not self.selected_platform_tag:
            self.warning_toast("", self.tra("请选择接口平台"))
            return
        
        model = self.model_combo.currentText().strip()
        if not model:
            self.warning_toast("", self.tra("请输入模型名称"))
            return
            
        # 构建返回数据
        data = {
            "name": name,
            "platform_tag": self.selected_platform_tag,
            "model": model,
        }

        # 根据平台类型获取不同字段
        if self.selected_platform_tag == "amazonbedrock":
            region = self.region_edit.text().strip()
            access_key = self.access_key_edit.toPlainText().strip()
            secret_key = self.secret_key_edit.toPlainText().strip()
            
            if not region:
                self.warning_toast("", self.tra("请输入区域"))
                return
            if not access_key:
                self.warning_toast("", self.tra("请输入 Access Key"))
                return
            if not secret_key:
                self.warning_toast("", self.tra("请输入 Secret Key"))
                return
            
            data["region"] = region
            data["access_key"] = access_key
            data["secret_key"] = secret_key

        else:
            api_url = self.url_edit.text().strip()
            api_key = self.api_key_edit.toPlainText().strip()
            
            # 仅当自定义时强校验 URL，其他情况有默认值或已隐藏
            if not api_url and self.selected_platform_tag == "custom":
                self.warning_toast("", self.tra("请输入接口地址"))
                return
            
            data["api_url"] = api_url
            data["api_key"] = api_key
            
            if self.selected_platform_tag == "custom":
                data["api_format"] = self.format_combo.currentText()
                data["auto_complete"] = self.auto_complete_switch.isChecked()
                
        if self.on_confirm:
            self.on_confirm(data)
            
        super().accept()