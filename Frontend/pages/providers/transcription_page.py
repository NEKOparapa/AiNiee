"""DashScope transcription configuration, separate from text-model bindings."""

import copy
import math
from urllib.parse import urlsplit
from uuid import uuid4

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    ComboBox,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SingleDirectionScrollArea,
    SpinBox,
    StrongBodyLabel,
    SwitchButton,
    TitleLabel,
)

from Frontend.components.toast import ToastMixin
from Frontend.core.base import Base
from Frontend.core.config import ConfigMixin


DEFAULT_TRANSCRIPTION_PLATFORM = {
    "name": "阿里云百炼",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "",
    "model": "qwen-audio-3.1-asr-flash",
    "api_format": "DashScope",
    "request_timeout": 300,
    "language_hints": [],
    "speaker_diarization_enabled": False,
    "chunk_duration_seconds": 240,
    "chunk_overlap_seconds": 2,
    "chunk_concurrency": 3,
    "vad_threshold": 0.35,
}
MIN_REQUEST_TIMEOUT = 10
MAX_REQUEST_TIMEOUT = 3600
# Public DashScope language codes; keep the desktop independent of Backend.
SUPPORTED_LANGUAGE_HINTS = frozenset(
    "zh en ja ko vi th id ms tl hi ar fr de es pt ru it nl sv da fi no el pl cs hu ro bg hr sk".split()
)


def normalize_transcription_platform(data: dict | None = None) -> dict:
    """Return a detached form value; accept comma-separated language input."""
    if data is not None and not isinstance(data, dict):
        raise ValueError("转录接口配置必须是对象。")
    result = copy.deepcopy(DEFAULT_TRANSCRIPTION_PLATFORM)
    result.update(copy.deepcopy(data or {}))
    for field in ("name", "api_url", "api_key", "model", "api_format"):
        if not isinstance(result[field], str):
            raise ValueError("接口名称、地址、密钥、模型和格式必须是文本。")
        result[field] = result[field].strip()

    timeout = result["request_timeout"]
    if isinstance(timeout, float) and timeout.is_integer():
        result["request_timeout"] = int(timeout)

    hints = result["language_hints"]
    if isinstance(hints, str):
        hints = hints.replace("，", ",").split(",")
    if not isinstance(hints, list) or any(not isinstance(hint, str) for hint in hints):
        raise ValueError("语言提示必须是逗号分隔的语言代码或文本列表。")
    result["language_hints"] = list(dict.fromkeys(hint.strip() for hint in hints if hint.strip()))
    return result


def validate_transcription_platform(data: dict, *, require_api_key: bool = False) -> dict:
    """Validate without I/O; errors never include submitted credentials."""
    result = normalize_transcription_platform(data)
    if not result["name"]:
        raise ValueError("请输入转录接口名称。")
    if result["api_format"] != "DashScope":
        raise ValueError("目前仅支持 DashScope 转录接口。")
    try:
        parsed = urlsplit(result["api_url"])
        valid_url = (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
            and not any(character.isspace() for character in result["api_url"])
        )
        parsed.port
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("请输入有效的 HTTP 或 HTTPS 接口地址，不要在地址中嵌入账号、密码或片段。")
    if not result["model"]:
        raise ValueError("请输入转录模型名称。")
    timeout = result["request_timeout"]
    if type(timeout) is not int or not MIN_REQUEST_TIMEOUT <= timeout <= MAX_REQUEST_TIMEOUT:
        raise ValueError("请求超时必须是 10 至 3600 秒之间的整数。")
    if type(result["speaker_diarization_enabled"]) is not bool:
        raise ValueError("说话人分离必须是开启或关闭。")
    if len(result["language_hints"]) > 4:
        raise ValueError("语言提示最多填写 4 种语言。")
    if any(hint not in SUPPORTED_LANGUAGE_HINTS for hint in result["language_hints"]):
        raise ValueError("语言提示请使用受支持的小写短码，例如 zh、en、ja，不接受 zh-CN 等地区码。")
    if require_api_key and not result["api_key"]:
        raise ValueError("请先填写并保存接口密钥，再激活此转录接口。")
    for key, lower, upper in (("chunk_duration_seconds", 30, 290), ("chunk_concurrency", 1, 8)):
        if type(result[key]) is not int or not lower <= result[key] <= upper:
            raise ValueError(f"{key} 必须为 {lower} 至 {upper} 的整数。")
    for key, lower, upper in (("chunk_overlap_seconds", 0.5, 5), ("vad_threshold", 0.01, 0.99)):
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{key} 必须为 {lower} 至 {upper} 之间的数字。")
    return result


def build_transcription_config_update(
    config: dict,
    platform_id: str,
    platform: dict | None = None,
    *,
    action: str = "save",
) -> dict:
    """Build only transcription keys, preserving unrelated providers and input."""
    if not isinstance(config, dict) or not isinstance(platform_id, str) or not platform_id.strip():
        raise ValueError("转录配置或接口标识无效。")
    providers = config.get("transcription_platforms", {})
    if not isinstance(providers, dict):
        raise ValueError("转录接口列表必须是对象。")
    providers = copy.deepcopy(providers)
    active = config.get("active_transcription_platform", "")
    if not isinstance(active, str):
        raise ValueError("激活的转录接口标识必须是文本。")
    if action == "save":
        if not isinstance(platform, dict):
            raise ValueError("请提供需要保存的转录接口配置。")
        previous = providers.get(platform_id, {})
        if not isinstance(previous, dict):
            raise ValueError("已有转录接口配置无效。")
        providers[platform_id] = validate_transcription_platform({**previous, **platform})
    elif action == "activate":
        if platform_id not in providers:
            raise ValueError("转录接口不存在，请刷新页面。")
        providers[platform_id] = validate_transcription_platform(providers[platform_id], require_api_key=True)
        active = platform_id
    elif action == "delete":
        if platform_id not in providers:
            raise ValueError("转录接口不存在，请刷新页面。")
        del providers[platform_id]
        if active == platform_id:
            active = ""
    else:
        raise ValueError("未知的转录配置操作。")
    return {"transcription_platforms": providers, "active_transcription_platform": active}


class TranscriptionPage(QFrame, ConfigMixin, ToastMixin, Base):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setObjectName(text.replace(" ", "-"))
        self._platforms = {}
        self._active_id = ""
        self._selected_id = ""
        self._baseline = None
        self._loading = False
        self._template = copy.deepcopy(DEFAULT_TRANSCRIPTION_PLATFORM)
        self._build_ui()
        self._set_editor_enabled(False)
        try:
            defaults = self.get_default_section("TranscriptionPage")
            self._template = normalize_transcription_platform(defaults.get("transcription_platforms", {}).get("bailian_asr"))
            self._apply_config(self.load_config())
        except Exception:
            self.error_toast(self.tra("读取失败"), self.tra("无法读取转录接口配置，请检查后端连接后刷新。"))

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(TitleLabel(self.tra("转录接口"), self))
        description = CaptionLabel(self.tra("管理音频转文字使用的独立接口。目前仅支持 DashScope；新增和删除立即保存，字段修改请点击保存。"), self)
        description.setWordWrap(True)
        layout.addWidget(description)
        self.active_label = StrongBodyLabel(self.tra("未激活转录接口"), self)
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
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.viewport().setObjectName("transcriptionViewport")
        scroll.viewport().setStyleSheet("QWidget#transcriptionViewport { background: transparent; }")
        content = QWidget()
        content.setObjectName("transcriptionContent")
        content.setStyleSheet("QWidget#transcriptionContent { background: transparent; }")
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
        self._add_field(fields, "转录模型", self.model_edit)
        self.timeout_spin = SpinBox(self.editor)
        self.timeout_spin.setRange(MIN_REQUEST_TIMEOUT, MAX_REQUEST_TIMEOUT)
        self.timeout_spin.setSuffix(self.tra(" 秒"))
        self._add_field(fields, "请求超时", self.timeout_spin)
        self.languages_edit = LineEdit(self.editor)
        self.languages_edit.setPlaceholderText("zh, en, ja")
        self._add_field(fields, "语言提示", self.languages_edit, "可选，最多 4 种语言。用逗号分隔受支持的小写短码，例如 zh, en, ja；不接受地区码，留空由模型识别语言。")
        self.speaker_switch = SwitchButton(self.editor)
        self._add_field(fields, "说话人分离", self.speaker_switch, "请求为不同说话人的内容添加区分标记。是否支持及返回效果取决于所选 DashScope 模型。")
        self.chunk_duration_spin = SpinBox(self.editor)
        self.chunk_duration_spin.setRange(30, 290)
        self.chunk_duration_spin.setSuffix(self.tra(" 秒"))
        self._add_field(fields, "长音频切片时长", self.chunk_duration_spin,
                        "超过 5 分钟的音频自动按语音停顿切片，保留重叠区间并恢复原始时间轴。此值是目标长度，实际切点会随停顿调整。")
        self.chunk_concurrency_spin = SpinBox(self.editor)
        self.chunk_concurrency_spin.setRange(1, 8)
        self._add_field(fields, "切片并发数", self.chunk_concurrency_spin,
                        "同时发送的转录请求数。遇到服务限流时可降低此值；已完成的切片可随中间模型继续使用。")
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
        for widget in (self.name_edit, self.url_edit, self.key_edit, self.model_edit, self.languages_edit):
            widget.textChanged.connect(self._update_edit_status)
        self.timeout_spin.valueChanged.connect(self._update_edit_status)
        self.chunk_duration_spin.valueChanged.connect(self._update_edit_status)
        self.chunk_concurrency_spin.valueChanged.connect(self._update_edit_status)
        self.speaker_switch.checkedChanged.connect(self._update_edit_status)

    def _add_field(self, layout, label, widget, description=""):
        layout.addWidget(StrongBodyLabel(self.tra(label), self.editor))
        layout.addWidget(widget)
        if description:
            caption = CaptionLabel(self.tra(description), self.editor)
            caption.setWordWrap(True)
            layout.addWidget(caption)
        layout.addSpacing(6)

    def _form_values(self):
        return {
            "name": self.name_edit.text(), "api_url": self.url_edit.text(),
            "api_key": self.key_edit.text(), "model": self.model_edit.text(),
            "api_format": self.format_combo.currentText(), "request_timeout": self.timeout_spin.value(),
            "language_hints": self.languages_edit.text(),
            "speaker_diarization_enabled": self.speaker_switch.isChecked(),
            "chunk_duration_seconds": self.chunk_duration_spin.value(),
            "chunk_concurrency": self.chunk_concurrency_spin.value(),
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
        platforms = config.get("transcription_platforms", {})
        if not isinstance(platforms, dict):
            raise ValueError("转录接口列表必须是对象。")
        self._platforms = copy.deepcopy(platforms)
        self._active_id = config.get("active_transcription_platform", "")
        self._selected_id = next((identifier for identifier in (preferred_id, self._selected_id, self._active_id) if identifier in platforms), next(iter(platforms), ""))
        self.provider_combo.blockSignals(True)
        try:
            self.provider_combo.clear()
            for identifier, platform in platforms.items():
                name = platform.get("name", identifier)
                self.provider_combo.addItem(name + (self.tra("（已激活）") if identifier == self._active_id else ""), userData=identifier)
            self.provider_combo.setCurrentIndex(self.provider_combo.findData(self._selected_id))
        finally:
            self.provider_combo.blockSignals(False)
        active = platforms.get(self._active_id)
        self.active_label.setText(self.tra("当前转录接口：") + active.get("name", self._active_id) if active else self.tra("未激活转录接口"))
        self._load_form()

    def _load_form(self):
        self._loading = True
        try:
            data = normalize_transcription_platform(self._platforms.get(self._selected_id))
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
            self.languages_edit.setText(", ".join(data["language_hints"]))
            self.speaker_switch.setChecked(data["speaker_diarization_enabled"])
            self.chunk_duration_spin.setValue(data["chunk_duration_seconds"])
            self.chunk_concurrency_spin.setValue(data["chunk_concurrency"])
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
        def update(current):
            current.update(build_transcription_config_update(current, platform_id, platform, action=action))
        try:
            config = self.update_config(update)
            self._apply_config(config, platform_id if action != "delete" else "")
            return True
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
        except Exception:
            # Do not display request bodies or credentials from network errors.
            self.error_toast(self.tra("保存失败"), self.tra("无法更新转录配置，请检查后端连接或刷新后重试。"))
        return False

    def _reload_config(self):
        if not self._confirm_discard():
            return
        try:
            self._apply_config(self.load_config())
        except Exception:
            self.error_toast(self.tra("读取失败"), self.tra("无法读取转录接口配置，请检查后端连接后重试。"))

    def _add_platform(self):
        if not self._confirm_discard():
            return
        platform = copy.deepcopy(self._template)
        platform["name"] = self.tra("新的转录接口")
        platform["api_key"] = ""
        if self._persist("dashscope_" + uuid4().hex, platform):
            self.success_toast(self.tra("已添加"), self.tra("转录配置已添加，请填写接口信息并保存。"))

    def _save_platform(self):
        if self._selected_id and self._persist(self._selected_id, self._form_values()):
            self.success_toast(self.tra("已保存"), self.tra("转录接口配置已保存。"))

    def _activate_platform(self):
        if self._is_dirty():
            self.warning_toast(self.tra("请先保存"), self.tra("请先保存当前修改，再激活此转录接口。"))
            return
        if self._selected_id and self._persist(self._selected_id, action="activate"):
            self.success_toast(self.tra("已激活"), self.tra("已切换当前使用的转录接口。"))

    def _delete_platform(self):
        if not self._selected_id:
            return
        content = self.tra("是否删除当前转录配置及其未保存的修改？")
        if self._selected_id == self._active_id:
            content += "\n" + self.tra("删除后将没有激活的转录接口。")
        dialog = MessageBox(self.tra("删除转录配置"), content, self.window())
        dialog.yesButton.setText(self.tra("删除"))
        dialog.cancelButton.setText(self.tra("取消"))
        if dialog.exec() and self._persist(self._selected_id, action="delete"):
            self.success_toast(self.tra("已删除"), self.tra("转录接口配置已删除。"))
