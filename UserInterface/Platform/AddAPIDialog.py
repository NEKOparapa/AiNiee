from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from qfluentwidgets import (
    CaptionLabel,
    ComboBox,
    EditableComboBox,
    FlowLayout,
    FluentIcon,
    LineEdit,
    MessageBoxBase,
    PillPushButton,
    PlainTextEdit,
    SingleDirectionScrollArea,
    SmoothMode,
    StrongBodyLabel,
    SwitchButton,
    TransparentToolButton,
)

# Fix Bug: 修复 qfluentwidgets 滚动条事件处理崩溃问题 ---
try:
    from qfluentwidgets.components.widgets.scroll_bar import SmoothScrollDelegate

    _original_eventFilter = SmoothScrollDelegate.eventFilter

    def _safe_eventFilter(self, obj, e):
        try:
            return _original_eventFilter(self, obj, e)
        except AttributeError:
            return False
        except Exception:
            return False

    SmoothScrollDelegate.eventFilter = _safe_eventFilter
except ImportError:
    pass


from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from UserInterface.Widget.Toast import ToastMixin


class AddAPIDialog(MessageBoxBase, ConfigMixin, ToastMixin, Base):
    """添加新接口的两步式对话框"""

    PAGE_BASIC = 0
    PAGE_DETAILS = 1

    def __init__(self, window, preset_platforms: dict, on_confirm=None):
        super().__init__(window)

        self.preset_platforms = preset_platforms
        self.on_confirm = on_confirm
        self.selected_platform_tag = None
        self.current_page = self.PAGE_BASIC
        self.platform_buttons = {}

        self._set_adaptive_size()

        self._build_ui()
        self._set_page(self.PAGE_BASIC)

    def _set_adaptive_size(self) -> None:
        dialog_width = 680
        target_height = 750
        min_height = 560
        vertical_margin = 48

        available_heights = []
        parent = self.parentWidget()
        if parent is not None and parent.height() > 0:
            available_heights.append(parent.height())

        screen = None
        if parent is not None:
            try:
                screen = parent.screen()
            except AttributeError:
                screen = None

        if screen is None:
            screen = QApplication.primaryScreen()

        if screen is not None:
            available_heights.append(screen.availableGeometry().height())

        available_height = min(available_heights) if available_heights else target_height + vertical_margin
        dialog_height = min(target_height, max(min_height, available_height - vertical_margin))
        self.widget.setFixedSize(dialog_width, dialog_height)

    def _build_ui(self):
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        self.viewLayout.setSpacing(16)

        header_widget = QWidget(self.widget)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        title = StrongBodyLabel(self.tra("添加新接口"), header_widget)
        title.setStyleSheet("font-size: 18px;")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self.close_button = TransparentToolButton(FluentIcon.CLOSE, header_widget)
        self.close_button.setFixedSize(32, 32)
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.setToolTip(self.tra("关闭"))
        self.close_button.clicked.connect(self._close_dialog)
        header_layout.addWidget(self.close_button, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.viewLayout.addWidget(header_widget)

        self.page_stack = QStackedWidget(self.widget)
        self.viewLayout.addWidget(self.page_stack, 1)

        self.page_stack.addWidget(self._create_basic_page())
        self.page_stack.addWidget(self._create_detail_page())

    def _create_basic_page(self) -> QWidget:
        page = QWidget(self.widget)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # --- 接口名称区域 ---
        name_layout = QVBoxLayout()
        name_layout.setSpacing(8)
        self._add_section_label(self.tra("接口名称"), name_layout)
        self.name_edit = LineEdit(page)
        self.name_edit.setPlaceholderText(self.tra("请输入接口名称，例如：我的 GPT 接口"))
        self.name_edit.setClearButtonEnabled(True)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # --- 接口平台头部 ---
        self._add_section_label(self.tra("选择接口平台"), layout)

        # --- 接口平台列表 (带滚动条) ---
        self.platform_scroll = SingleDirectionScrollArea(orient=Qt.Vertical)
        self.platform_scroll.setSmoothMode(SmoothMode.NO_SMOOTH)
        self.platform_scroll.setWidgetResizable(True)
        self.platform_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        self.platform_layout = QVBoxLayout(scroll_widget)
        self.platform_layout.setContentsMargins(0, 0, 12, 8)
        self.platform_layout.setSpacing(16)  # 分组之间的间距

        self._init_platform_buttons(self.platform_layout)
        self.platform_layout.addStretch(1)

        self.platform_scroll.setWidget(scroll_widget)
        layout.addWidget(self.platform_scroll, 1)

        return page

    def _create_detail_page(self) -> QWidget:
        page = QWidget(self.widget)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll_area = SingleDirectionScrollArea(orient=Qt.Vertical)
        self.scroll_area.setSmoothMode(SmoothMode.NO_SMOOTH)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_widget = QWidget()
        scroll_widget.setObjectName("addApiScrollWidget")
        scroll_widget.setStyleSheet("#addApiScrollWidget { background: transparent; }")

        self.scroll_layout = QVBoxLayout(scroll_widget)
        self.scroll_layout.setContentsMargins(0, 8, 12, 8)
        self.scroll_layout.setSpacing(12)
        self.scroll_area.setWidget(scroll_widget)

        layout.addWidget(self.scroll_area)

        self.url_label = self._add_section_label(self.tra("接口地址"), self.scroll_layout)
        self.url_edit = LineEdit(scroll_widget)
        self.url_edit.setPlaceholderText(self.tra("请输入接口地址，例如：https://api.openai.com/v1"))
        self.url_edit.setClearButtonEnabled(True)
        self.scroll_layout.addWidget(self.url_edit)

        self.api_key_label = self._add_section_label(self.tra("接口密钥"), self.scroll_layout)
        self.api_key_edit = PlainTextEdit(scroll_widget)
        self.api_key_edit.setPlaceholderText(
            self.tra("请输入接口密钥，例如：sk-xxxxxxxx，多个密钥之间请使用半角逗号（,）分隔")
        )
        self.api_key_edit.setFixedHeight(80)
        self.scroll_layout.addWidget(self.api_key_edit)

        self.region_label = self._add_section_label(self.tra("区域"), self.scroll_layout)
        self.region_edit = LineEdit(scroll_widget)
        self.region_edit.setPlaceholderText(self.tra("请输入区域，例如：us-east-1"))
        self.scroll_layout.addWidget(self.region_edit)

        self.access_key_label = self._add_section_label(self.tra("AWS Access Key"), self.scroll_layout)
        self.access_key_edit = LineEdit(scroll_widget)
        self.access_key_edit.setPlaceholderText(self.tra("请输入 AWS Access Key ID"))
        self.scroll_layout.addWidget(self.access_key_edit)

        self.secret_key_label = self._add_section_label(self.tra("AWS Secret Key"), self.scroll_layout)
        self.secret_key_edit = LineEdit(scroll_widget)
        self.secret_key_edit.setPlaceholderText(self.tra("请输入 AWS Secret Access Key"))
        self.scroll_layout.addWidget(self.secret_key_edit)

        self.model_label = self._add_section_label(self.tra("模型名称"), self.scroll_layout)
        self.model_combo = EditableComboBox(scroll_widget)
        self.model_combo.setPlaceholderText(self.tra("请输入或选择模型名称"))
        self.scroll_layout.addWidget(self.model_combo)

        self.custom_options_container = QFrame(scroll_widget)
        custom_options_layout = QVBoxLayout(self.custom_options_container)
        custom_options_layout.setContentsMargins(0, 0, 0, 0)
        custom_options_layout.setSpacing(12)

        format_label = StrongBodyLabel(self.tra("接口格式"), self.custom_options_container)
        custom_options_layout.addWidget(format_label)

        self.format_combo = ComboBox(self.custom_options_container)
        self.format_combo.addItems(["OpenAI", "Anthropic", "Google"])
        custom_options_layout.addWidget(self.format_combo)

        auto_complete_row = QHBoxLayout()
        auto_complete_row.setContentsMargins(0, 0, 0, 0)

        auto_complete_label = StrongBodyLabel(self.tra("接口地址自动补全"), self.custom_options_container)
        self.auto_complete_switch = SwitchButton(self.custom_options_container)
        self.auto_complete_switch.setChecked(True)
        auto_complete_row.addWidget(auto_complete_label)
        auto_complete_row.addStretch(1)
        auto_complete_row.addWidget(self.auto_complete_switch)
        custom_options_layout.addLayout(auto_complete_row)

        auto_complete_desc = CaptionLabel(self.tra("自动为接口地址添加 /v1 后缀"), self.custom_options_container)
        auto_complete_desc.setStyleSheet("color: #888;")
        custom_options_layout.addWidget(auto_complete_desc)

        self.scroll_layout.addWidget(self.custom_options_container)
        self.custom_options_container.setVisible(False)

        self._set_bedrock_fields_visible(False)
        self.scroll_layout.addStretch(1)

        return page

    def _add_section_label(self, text: str, layout: QVBoxLayout):
        """通用添加标签方法"""
        label = StrongBodyLabel(text)
        layout.addWidget(label)
        return label

    def _set_page(self, page_index: int) -> None:
        self.current_page = page_index
        self.page_stack.setCurrentIndex(page_index)

        if page_index == self.PAGE_BASIC:
            self.cancelButton.setText(self.tra("取消"))
            self.yesButton.setText(self.tra("下一步"))
        else:
            self.cancelButton.setText(self.tra("上一步"))
            self.yesButton.setText(self.tra("确认"))

    def _close_dialog(self) -> None:
        super().reject()

    def _set_bedrock_fields_visible(self, visible: bool):
        """控制 Amazon Bedrock 专用字段的显隐"""
        self.region_label.setVisible(visible)
        self.region_edit.setVisible(visible)
        self.access_key_label.setVisible(visible)
        self.access_key_edit.setVisible(visible)
        self.secret_key_label.setVisible(visible)
        self.secret_key_edit.setVisible(visible)

    def _create_platform_group(self, title: str, platforms: dict, layout: QVBoxLayout):
        """创建卡片式的平台分组"""
        if not platforms:
            return

        # 卡片容器 (使用半透明边框，自适应亮/暗色模式)
        group_container = QFrame()
        group_container.setStyleSheet("""
            QFrame {
                border: 1px solid rgba(128, 128, 128, 0.2);
                border-radius: 8px;
                background-color: transparent;
            }
        """)
        group_layout = QVBoxLayout(group_container)
        group_layout.setContentsMargins(16, 12, 16, 16)
        group_layout.setSpacing(12)

        # 分组标题
        title_label = CaptionLabel(title)
        title_label.setStyleSheet("color: #888; font-weight: bold; border: none;")
        group_layout.addWidget(title_label)

        # 按钮流式布局 (关闭 needAni 动画)
        flow_widget = QWidget()
        flow_widget.setStyleSheet("border: none;")
        flow_layout = FlowLayout(flow_widget, needAni=False)
        flow_layout.setContentsMargins(0, 0, 0, 0)
        flow_layout.setHorizontalSpacing(10)
        flow_layout.setVerticalSpacing(10)

        for tag, platform in platforms.items():
            btn = PillPushButton(platform.get("name", tag))
            btn.setCheckable(True)
            btn.setMinimumSize(90, 32) # 增加按钮触摸面积
            btn.clicked.connect(lambda checked, t=tag: self._on_platform_selected(t))
            self.platform_buttons[tag] = btn
            flow_layout.addWidget(btn)

        group_layout.addWidget(flow_widget)
        layout.addWidget(group_container)

    def _init_platform_buttons(self, layout: QVBoxLayout):
            """初始化平台选择按钮（采用分组卡片式设计）"""
            local_platforms = {k: v for k, v in self.preset_platforms.items() if v.get("group") == "local"}
            online_platforms = {k: v for k, v in self.preset_platforms.items() if v.get("group") == "online"}
            other_platforms = {}
            if "custom" in self.preset_platforms:
                other_platforms["custom"] = self.preset_platforms["custom"]

            # 动态拼接 Emoji 与翻译后的文本，确保多语言匹配正常
            local_title = f"💻 {self.tra('本地模型')}"
            online_title = f"☁️ {self.tra('官方接口')}"
            other_title = f"⚙️ {self.tra('其他')}"

            # 分区创建卡片
            self._create_platform_group(local_title, local_platforms, layout)
            self._create_platform_group(online_title, online_platforms, layout)
            self._create_platform_group(other_title, other_platforms, layout)

    def _on_platform_selected(self, tag: str):
        """处理平台选择，根据配置文件填充默认数据"""
        for current_tag, btn in self.platform_buttons.items():
            btn.setChecked(current_tag == tag)

        self.selected_platform_tag = tag

        platform = self.preset_platforms.get(tag, {})
        group = platform.get("group", "")

        model_datas = platform.get("model_datas", [])
        self.model_combo.clear()
        self.model_combo.addItems(model_datas)
        if model_datas:
            default_model = platform.get("model", model_datas[0])
            idx = self.model_combo.findText(default_model)
            self.model_combo.setCurrentIndex(max(0, idx))

        format_datas = platform.get("format_datas", ["OpenAI", "Anthropic", "Google"])
        default_format = platform.get("api_format", "OpenAI")
        self.format_combo.clear()
        self.format_combo.addItems(format_datas)
        self.format_combo.setCurrentIndex(max(0, self.format_combo.findText(default_format)))

        auto_complete_default = platform.get("auto_complete", True)
        self.auto_complete_switch.setChecked(auto_complete_default)

        if tag == "amazonbedrock":
            self.url_label.setVisible(False)
            self.url_edit.setVisible(False)
            self.api_key_label.setVisible(False)
            self.api_key_edit.setVisible(False)

            self._set_bedrock_fields_visible(True)
            self.custom_options_container.setVisible(False)

            self.region_edit.setText(platform.get("region", ""))
            self.access_key_edit.clear()
            self.secret_key_edit.clear()

        elif tag == "custom":
            self.url_label.setVisible(True)
            self.url_edit.setVisible(True)
            self.url_edit.setEnabled(True)
            self.url_edit.setText(platform.get("api_url", ""))
            self.url_edit.setPlaceholderText(self.tra("请输入接口地址"))

            self.api_key_label.setVisible(True)
            self.api_key_edit.setVisible(True)
            self.api_key_edit.setPlainText(platform.get("api_key", ""))

            self._set_bedrock_fields_visible(False)
            self.custom_options_container.setVisible(True)

        elif group == "local":
            self.url_label.setVisible(True)
            self.url_edit.setVisible(True)
            self.url_edit.setEnabled(True)
            self.url_edit.setText(platform.get("api_url", ""))
            self.url_edit.setPlaceholderText(self.tra("请输入接口地址"))

            self.api_key_label.setVisible(False)
            self.api_key_edit.setVisible(False)
            self.api_key_edit.setPlainText(platform.get("api_key", ""))

            self._set_bedrock_fields_visible(False)
            self.custom_options_container.setVisible(False)

        else:
            self.url_label.setVisible(False)
            self.url_edit.setVisible(False)
            self.url_edit.setText(platform.get("api_url", ""))

            self.api_key_label.setVisible(True)
            self.api_key_edit.setVisible(True)
            self.api_key_edit.setPlainText(platform.get("api_key", ""))

            self._set_bedrock_fields_visible(False)
            self.custom_options_container.setVisible(False)

    def _validate_basic_page(self) -> bool:
        name = self.name_edit.text().strip()
        if not name:
            self.warning_toast("", self.tra("请输入接口名称"))
            return False

        if not self.selected_platform_tag:
            self.warning_toast("", self.tra("请选择接口平台"))
            return False

        return True

    def _build_submit_data(self) -> dict | None:
        model = self.model_combo.currentText().strip()
        if not model:
            self.warning_toast("", self.tra("请输入模型名称"))
            return None

        data = {
            "name": self.name_edit.text().strip(),
            "platform_tag": self.selected_platform_tag,
            "model": model,
        }

        if self.selected_platform_tag == "amazonbedrock":
            region = self.region_edit.text().strip()
            access_key = self.access_key_edit.text().strip()
            secret_key = self.secret_key_edit.text().strip()

            if not region:
                self.warning_toast("", self.tra("请输入区域"))
                return None
            if not access_key:
                self.warning_toast("", self.tra("请输入 Access Key"))
                return None
            if not secret_key:
                self.warning_toast("", self.tra("请输入 Secret Key"))
                return None

            data["region"] = region
            data["access_key"] = access_key
            data["secret_key"] = secret_key
            return data

        api_url = self.url_edit.text().strip()
        api_key = self.api_key_edit.toPlainText().strip()

        if not api_url and self.selected_platform_tag == "custom":
            self.warning_toast("", self.tra("请输入接口地址"))
            return None

        data["api_url"] = api_url
        data["api_key"] = api_key

        if self.selected_platform_tag == "custom":
            data["api_format"] = self.format_combo.currentText()
            data["auto_complete"] = self.auto_complete_switch.isChecked()

        return data

    def accept(self):
        """第一页下一步，第二页确认添加"""
        if self.current_page == self.PAGE_BASIC:
            if self._validate_basic_page():
                self._set_page(self.PAGE_DETAILS)
            return

        data = self._build_submit_data()
        if data is None:
            return

        if self.on_confirm:
            self.on_confirm(data)

        super().accept()

    def reject(self):
        """第一页取消关闭，第二页返回上一步"""
        if self.current_page == self.PAGE_DETAILS:
            self._set_page(self.PAGE_BASIC)
            return

        super().reject()
