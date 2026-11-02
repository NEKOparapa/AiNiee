"""Independent DashScope image-editing configuration for image translation."""
import copy
from uuid import uuid4

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel, CardWidget, ComboBox, LineEdit, MessageBox, PlainTextEdit,
    PrimaryPushButton, PushButton, SingleDirectionScrollArea, SpinBox,
    StrongBodyLabel, SwitchButton, TitleLabel,
)

from Frontend.components.toast import ToastMixin
from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin
from Frontend.core.image_generation_config import (
    DEFAULT_IMAGE_GENERATION_PLATFORM, MAX_REQUEST_TIMEOUT, MAX_SEED, MIN_REQUEST_TIMEOUT,
    build_image_generation_config_update, normalize_image_generation_platform,
)


class ImageGenerationPage(QFrame, ConfigMixin, ToastMixin, Base):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName(text.replace(" ", "-"))
        self._platforms = {}
        self._active_id = ""
        self._selected_id = ""
        self._baseline = None
        self._loading = False
        self._template = copy.deepcopy(DEFAULT_IMAGE_GENERATION_PLATFORM)
        self._build_ui()
        self._set_editor_enabled(False)
        try:
            defaults = self.get_default_section("ImageGenerationPage")
            self._template = normalize_image_generation_platform(
                defaults.get("image_generation_platforms", {}).get("bailian_image"))
            self._apply_config(self.load_config())
        except Exception:
            self.error_toast(self.tra("读取失败"), self.tra("无法读取生图接口配置，请检查后端连接后刷新。"))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(TitleLabel(self.tra("生图接口"), self))
        description = CaptionLabel(self.tra("配置用于图片翻译的独立图像编辑接口。模型会编辑整张图片，结果请人工对照原图。"), self)
        description.setWordWrap(True)
        layout.addWidget(description)
        self.active_label = StrongBodyLabel(self.tra("未激活生图接口"), self)
        layout.addWidget(self.active_label)

        selection = QHBoxLayout()
        self.provider_combo = ComboBox(self)
        self.provider_combo.setMinimumWidth(220)
        self.provider_combo.currentIndexChanged.connect(self._select_platform)
        selection.addWidget(self.provider_combo, 1)
        self.add_button = PushButton(self.tra("新增配置"), self)
        self.add_button.clicked.connect(self._add_platform)
        selection.addWidget(self.add_button)
        self.delete_button = PushButton(self.tra("删除配置"), self)
        self.delete_button.clicked.connect(self._delete_platform)
        selection.addWidget(self.delete_button)
        self.refresh_button = PushButton(self.tra("刷新"), self)
        self.refresh_button.clicked.connect(self._reload_config)
        selection.addWidget(self.refresh_button)
        layout.addLayout(selection)

        scroll = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        self.scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.viewport().setObjectName("imageGenerationViewport")
        scroll.viewport().setStyleSheet("QWidget#imageGenerationViewport { background: transparent; }")
        content = QWidget()
        content.setObjectName("imageGenerationContent")
        content.setStyleSheet("QWidget#imageGenerationContent { background: transparent; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        self.editor = CardWidget(content)
        fields = QVBoxLayout(self.editor)
        fields.setContentsMargins(20, 16, 20, 20)
        fields.setSpacing(8)
        self.name_edit = LineEdit(self.editor)
        self._add_field(fields, "配置名称", self.name_edit)
        self.format_combo = ComboBox(self.editor)
        self.format_combo.addItem("DashScope")
        self.format_combo.setEnabled(False)
        self._add_field(fields, "接口格式", self.format_combo)
        self.url_edit = LineEdit(self.editor)
        self._add_field(fields, "接口地址", self.url_edit)
        self.key_edit = LineEdit(self.editor)
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText(self.tra("请输入此接口的 API Key"))
        self._add_field(fields, "接口密钥", self.key_edit)
        self.model_edit = LineEdit(self.editor)
        self._add_field(fields, "生图模型", self.model_edit)
        self.timeout_spin = SpinBox(self.editor)
        self.timeout_spin.setRange(MIN_REQUEST_TIMEOUT, MAX_REQUEST_TIMEOUT)
        self.timeout_spin.setSuffix(self.tra(" 秒"))
        self._add_field(fields, "请求超时", self.timeout_spin)
        self.size_edit = LineEdit(self.editor)
        self.size_edit.setPlaceholderText("auto / 1536*1024")
        self._add_field(fields, "输出尺寸", self.size_edit,
                        "填写 auto 由接口选择尺寸，或填写 WIDTH*HEIGHT。实际尺寸范围由模型决定。")
        self.seed_edit = LineEdit(self.editor)
        self.seed_edit.setValidator(QIntValidator(0, MAX_SEED, self.seed_edit))
        self.seed_edit.setPlaceholderText(self.tra("留空使用随机种子"))
        self._add_field(fields, "随机种子", self.seed_edit,
                        "可填写 0 至 2147483647 的整数；固定种子不保证不同模型返回相同图片。")
        self.prompt_extend_switch = SwitchButton(self.editor)
        self._add_field(fields, "自动改写提示词", self.prompt_extend_switch)
        self.prompt_edit = PlainTextEdit(self.editor)
        self.prompt_edit.setMinimumHeight(110)
        self.prompt_edit.setMaximumHeight(180)
        self.prompt_edit.setPlaceholderText(self.tra("例如：保留角色外观、画面布局与原有画风。"))
        self._add_field(fields, "补充翻译要求", self.prompt_edit,
                        "在翻译任务要求之外追加；源语言和目标语言由图片工作区设置。")
        content_layout.addWidget(self.editor)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        actions = QHBoxLayout()
        self.edit_status_label = CaptionLabel("", self)
        actions.addWidget(self.edit_status_label, 1)
        self.save_button = PrimaryPushButton(self.tra("保存配置"), self)
        self.save_button.clicked.connect(self._save_platform)
        actions.addWidget(self.save_button)
        self.activate_button = PushButton(self.tra("激活此配置"), self)
        self.activate_button.clicked.connect(self._activate_platform)
        actions.addWidget(self.activate_button)
        layout.addLayout(actions)
        for widget in (self.name_edit, self.url_edit, self.key_edit, self.model_edit, self.size_edit, self.seed_edit):
            widget.textChanged.connect(self._update_edit_status)
        self.timeout_spin.valueChanged.connect(self._update_edit_status)
        self.prompt_edit.textChanged.connect(self._update_edit_status)
        self.prompt_extend_switch.checkedChanged.connect(self._update_edit_status)

    def _add_field(self, layout, label, widget, description=""):
        layout.addWidget(StrongBodyLabel(self.tra(label), self.editor))
        layout.addWidget(widget)
        if description:
            caption = CaptionLabel(self.tra(description), self.editor)
            caption.setWordWrap(True)
            layout.addWidget(caption)
        layout.addSpacing(6)

    def _form_values(self):
        seed = self.seed_edit.text().strip()
        # Dirty tracking must also work while a field contains incomplete input.
        if not seed:
            seed = None
        elif seed.isascii() and seed.isdigit() and len(seed) < 20:
            seed = int(seed)
        return {
            "name": self.name_edit.text(), "api_url": self.url_edit.text(),
            "api_key": self.key_edit.text(), "model": self.model_edit.text(),
            "api_format": self.format_combo.currentText(), "request_timeout": self.timeout_spin.value(),
            "size": self.size_edit.text(), "seed": seed,
            "prompt_extend": self.prompt_extend_switch.isChecked(), "prompt": self.prompt_edit.toPlainText(),
        }

    def _is_dirty(self):
        return self._baseline is not None and self._form_values() != self._baseline

    def _update_edit_status(self, *_):
        if not self._loading:
            self.edit_status_label.setText(self.tra("有未保存的修改") if self._is_dirty() else "")

    def _confirm_discard(self):
        if not self._is_dirty():
            return True
        dialog = MessageBox(self.tra("未保存的修改"), self.tra("当前配置的修改尚未保存，是否放弃这些修改？"), self.window())
        dialog.yesButton.setText(self.tra("放弃修改"))
        dialog.cancelButton.setText(self.tra("继续编辑"))
        return bool(dialog.exec())

    def prepare_to_leave(self):
        if not self._confirm_discard():
            return False
        if self._is_dirty():
            self._load_form()
        return True

    def _set_editor_enabled(self, enabled):
        self.editor.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.activate_button.setEnabled(enabled and self._selected_id != self._active_id)

    def _apply_config(self, config, preferred_id=""):
        platforms = config.get("image_generation_platforms", {})
        if not isinstance(platforms, dict) or any(not isinstance(value, dict) for value in platforms.values()):
            raise ValueError("生图接口列表必须是对象。")
        self._platforms = copy.deepcopy(platforms)
        self._active_id = config.get("active_image_generation_platform", "")
        self._selected_id = next((identifier for identifier in (preferred_id, self._selected_id, self._active_id)
                                  if identifier in platforms), next(iter(platforms), ""))
        self.provider_combo.blockSignals(True)
        try:
            self.provider_combo.clear()
            for identifier, platform in platforms.items():
                name = str(platform.get("name", identifier))
                self.provider_combo.addItem(name + (self.tra("（已激活）") if identifier == self._active_id else ""), userData=identifier)
            self.provider_combo.setCurrentIndex(self.provider_combo.findData(self._selected_id))
        finally:
            self.provider_combo.blockSignals(False)
        active = platforms.get(self._active_id)
        self.active_label.setText(self.tra("当前生图接口：") + str(active.get("name", self._active_id))
                                  if active else self.tra("未激活生图接口"))
        self._load_form()

    def _load_form(self):
        self._loading = True
        try:
            data = normalize_image_generation_platform(self._platforms.get(self._selected_id))
            self.name_edit.setText(data["name"])
            self.url_edit.setText(data["api_url"])
            self.key_edit.setText(data["api_key"])
            self.model_edit.setText(data["model"])
            self.format_combo.clear()
            self.format_combo.addItem("DashScope")
            if data["api_format"] != "DashScope":
                self.format_combo.addItem(data["api_format"])
            self.format_combo.setCurrentText(data["api_format"])
            self.timeout_spin.setValue(data["request_timeout"])
            self.size_edit.setText(data["size"])
            self.seed_edit.setText("" if data["seed"] is None else str(data["seed"]))
            self.prompt_extend_switch.setChecked(data["prompt_extend"])
            self.prompt_edit.setPlainText(data["prompt"])
            self._baseline = self._form_values() if self._selected_id else None
            self._set_editor_enabled(bool(self._selected_id))
        finally:
            self._loading = False
        self._update_edit_status()

    def _select_platform(self, index):
        selected = self.provider_combo.itemData(index)
        if not selected or selected == self._selected_id:
            return
        if not self._confirm_discard():
            self.provider_combo.blockSignals(True)
            self.provider_combo.setCurrentIndex(self.provider_combo.findData(self._selected_id))
            self.provider_combo.blockSignals(False)
            return
        self._selected_id = selected
        self._load_form()

    def _persist(self, platform_id, platform=None, *, action="save"):
        expected_exists = platform_id in self._platforms

        def update(current):
            if expected_exists and platform_id not in current.get("image_generation_platforms", {}):
                raise ValueError("配置已被其他操作删除，请刷新后重试。")
            current.update(build_image_generation_config_update(current, platform_id, platform, action=action))
        try:
            config = self.update_config(update)
            self._apply_config(config, platform_id if action != "delete" else "")
            return True
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
        except Exception:
            self.error_toast(self.tra("保存失败"), self.tra("无法更新生图配置，请检查后端连接或刷新后重试。"))
        return False

    def _reload_config(self):
        if not self._confirm_discard():
            return
        try:
            self._apply_config(self.load_config())
        except Exception:
            self.error_toast(self.tra("读取失败"), self.tra("无法读取生图接口配置，请检查后端连接后重试。"))

    def _add_platform(self):
        if not self._confirm_discard():
            return
        platform = copy.deepcopy(self._template)
        platform["name"] = self.tra("新的生图接口")
        platform["api_key"] = ""
        if self._persist("image_" + uuid4().hex, platform):
            self.success_toast(self.tra("已添加"), self.tra("生图配置已添加，请填写接口信息并保存。"))

    def _save_platform(self):
        if self._selected_id and self._persist(self._selected_id, self._form_values()):
            self.success_toast(self.tra("已保存"), self.tra("生图接口配置已保存。"))

    def _activate_platform(self):
        if self._is_dirty():
            self.warning_toast(self.tra("请先保存"), self.tra("请先保存当前修改，再激活此生图接口。"))
            return
        if self._selected_id and self._persist(self._selected_id, action="activate"):
            self.success_toast(self.tra("已激活"), self.tra("已切换当前使用的生图接口。"))

    def _delete_platform(self):
        if not self._selected_id:
            return
        content = self.tra("是否删除当前生图配置及其未保存的修改？")
        if self._selected_id == self._active_id:
            content += "\n" + self.tra("删除后将没有激活的生图接口。")
        dialog = MessageBox(self.tra("删除生图配置"), content, self.window())
        dialog.yesButton.setText(self.tra("删除"))
        dialog.cancelButton.setText(self.tra("取消"))
        if dialog.exec() and self._persist(self._selected_id, action="delete"):
            self.success_toast(self.tra("已删除"), self.tra("生图接口配置已删除。"))
