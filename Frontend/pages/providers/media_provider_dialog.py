"""Two-step provider creation and a compact, automatically saved editor."""

import copy

from PyQt5.QtCore import QSize, Qt, QTimer, QSignalBlocker, pyqtSignal
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLineEdit, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel, ComboBox, FluentIcon, FlowLayout, LineEdit, MessageBoxBase,
    PillPushButton, SingleDirectionScrollArea, StrongBodyLabel,
    SubtitleLabel, TransparentToolButton,
)

from Frontend.components.cards.spin_card import SpinCard
from Frontend.components.toast import ToastMixin
from Frontend.core.config import ConfigMixin
from Frontend.core.media_provider_config import (
    PROVIDER_FORMATS,
    get_media_provider_presets, normalize_media_provider, validate_media_provider,
)


class MediaProviderForm(QWidget, ConfigMixin):
    changed = pyqtSignal()
    editingFinished = pyqtSignal()

    def __init__(self, kind, parent=None, *, show_name=True):
        super().__init__(parent)
        self.kind = kind
        self._loading = False
        self._base_data = {}
        self.fields = QVBoxLayout(self)
        self.fields.setContentsMargins(0, 4, 8, 8)
        self.fields.setSpacing(14)
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText(self.tra("请输入接口名称"))
        self.name_row = self._add_field("接口名称", self.name_edit)
        self.name_row.setVisible(show_name)
        self.format_combo = ComboBox(self)
        self.format_combo.addItems(list(PROVIDER_FORMATS[kind]))
        self._add_field("接口格式", self.format_combo)
        self.url_edit = LineEdit(self)
        self.url_edit.setPlaceholderText("https://")
        self._add_field("接口地址", self.url_edit)
        self.key_edit = LineEdit(self)
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText(self.tra("请输入此接口的 API Key"))
        self._add_field("接口密钥", self.key_edit)
        self.app_id_edit = LineEdit(self)
        self.app_id_edit.setPlaceholderText(self.tra("可选，使用新 API Key 时留空"))
        self.app_id_row = self._add_field("APP ID", self.app_id_edit)
        self.resource_id_edit = LineEdit(self)
        self.resource_id_row = self._add_field("资源 ID", self.resource_id_edit)
        self.model_edit = LineEdit(self)
        self.model_edit.setPlaceholderText(self.tra("请输入模型名称或 Endpoint ID"))
        self._add_field("模型名称", self.model_edit)
        self.protocol_hint = CaptionLabel(self.tra("填写 Gemini API 基地址，模型名称单独填写。"), self)
        self.protocol_hint.setWordWrap(True)
        self.fields.addWidget(self.protocol_hint)
        self.fields.addStretch(1)
        for editor in (self.name_edit, self.url_edit, self.key_edit, self.app_id_edit,
                       self.resource_id_edit, self.model_edit):
            editor.textChanged.connect(self._changed)
            editor.editingFinished.connect(self._editing_finished)
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        self._sync_format_fields()

    def _add_field(self, title, widget):
        row = QWidget(self)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = StrongBodyLabel(self.tra(title), row)
        label.setBuddy(widget)
        layout.addWidget(label)
        layout.addWidget(widget)
        self.fields.addWidget(row)
        return row

    def _changed(self, *_):
        if not self._loading:
            self.changed.emit()

    def _editing_finished(self):
        if not self._loading:
            self.editingFinished.emit()

    def _format_changed(self, *_):
        format_ = self.format_combo.currentText()
        if not self._loading and self.kind == "transcription" and format_ == "VolcengineASRFast":
            if not self.model_edit.text().strip():
                self.model_edit.setText("bigmodel")
            if not self.resource_id_edit.text().strip():
                self.resource_id_edit.setText("volc.bigasr.auc_turbo")
        self._sync_format_fields()
        self._changed()

    def _sync_format_fields(self):
        format_ = self.format_combo.currentText()
        volcengine_asr = self.kind == "transcription" and format_ == "VolcengineASRFast"
        self.app_id_row.setVisible(volcengine_asr)
        self.resource_id_row.setVisible(volcengine_asr)
        self.key_edit.setPlaceholderText(self.tra("请输入 API Key 或 Access Token") if volcengine_asr
                                        else self.tra("请输入此接口的 API Key"))
        gemini = self.kind == "image_generation" and format_ == "Gemini"
        self.protocol_hint.setVisible(gemini)
        self.url_edit.setPlaceholderText("https://generativelanguage.googleapis.com" if gemini else "https://")
        self.model_edit.setPlaceholderText("gemini-3-pro-image" if gemini else self.tra("请输入模型名称或 Endpoint ID"))

    def load(self, data):
        values = normalize_media_provider(self.kind, data)
        self._loading = True
        try:
            self._base_data = copy.deepcopy(values)
            self.name_edit.setText(values["name"])
            self.format_combo.clear()
            formats = list(PROVIDER_FORMATS[self.kind]) if values.get("group") == "custom" else [values["api_format"]]
            if values["api_format"] not in formats:
                formats.append(values["api_format"])
            self.format_combo.addItems(formats)
            self.format_combo.setCurrentText(values["api_format"])
            self.format_combo.setEnabled(values.get("group") == "custom" and len(formats) > 1)
            self.url_edit.setText(values["api_url"])
            self.key_edit.setText(values["api_key"])
            self.app_id_edit.setText(values.get("app_id", ""))
            self.resource_id_edit.setText(values.get("resource_id", ""))
            self.model_edit.setText(values["model"])
            self._sync_format_fields()
        finally:
            self._loading = False

    def values(self):
        values = {
            "name": self.name_edit.text(), "api_format": self.format_combo.currentText(),
            "api_url": self.url_edit.text(), "api_key": self.key_edit.text(),
            "model": self.model_edit.text(),
        }
        if self.kind == "transcription" and values["api_format"] == "VolcengineASRFast":
            values.update(app_id=self.app_id_edit.text(), resource_id=self.resource_id_edit.text())
        return values

    def validate(self):
        return validate_media_provider(self.kind, {**self._base_data, **self.values()})


class _ProviderDialog(MessageBoxBase, ConfigMixin, ToastMixin):
    def __init__(self, title, parent):
        super().__init__(parent)
        screen = parent.screen() if parent is not None else QApplication.primaryScreen()
        available_height = min(parent.height(), screen.availableGeometry().height()) if screen else parent.height()
        self.widget.setFixedSize(min(680, max(440, parent.width() - 48)),
                                 min(750, max(400, available_height - 48)))
        self.viewLayout.setContentsMargins(24, 20, 24, 20)
        self.viewLayout.setSpacing(16)
        header = QHBoxLayout()
        self.title_label = SubtitleLabel(self.tra(title), self.widget)
        header.addWidget(self.title_label, 1)
        self.close_button = TransparentToolButton(FluentIcon.CLOSE, self.widget)
        self.close_button.setFixedSize(32, 32)
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.setToolTip(self.tra("关闭"))
        self.close_button.setAccessibleName(self.tra("关闭"))
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.close_button)
        self.viewLayout.addLayout(header)

    def _scroll(self, widget):
        scroll = SingleDirectionScrollArea(self.widget, orient=Qt.Vertical)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        widget.setObjectName("mediaProviderDialogContent")
        widget.setStyleSheet("QWidget#mediaProviderDialogContent { background: transparent; }")
        scroll.setWidget(widget)
        return scroll


class AddMediaProviderDialog(_ProviderDialog):
    def __init__(self, kind, parent, *, on_confirm):
        super().__init__("添加接口", parent)
        self.kind = kind
        self.on_confirm = on_confirm
        self.presets = get_media_provider_presets(kind)
        self.selected_preset = None
        self._loaded_preset = None
        self._committed = False
        self.platform_buttons = {}
        self.step_label = CaptionLabel(self.tra("1 / 2 · 名称与平台"), self.widget)
        self.step_label.setTextColor("#686868", "#aaaaaa")
        self.viewLayout.addWidget(self.step_label)
        self.page_stack = QStackedWidget(self.widget)
        self.viewLayout.addWidget(self.page_stack, 1)
        basic = QWidget(self.widget)
        layout = QVBoxLayout(basic)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(StrongBodyLabel(self.tra("接口名称"), basic))
        self.name_edit = LineEdit(basic)
        self.name_edit.setPlaceholderText(self.tra("请输入接口名称"))
        layout.addWidget(self.name_edit)
        for group, title in (("online", "官方接口"), ("custom", "自定义接口")):
            layout.addWidget(StrongBodyLabel(self.tra(title), basic))
            choices = QWidget(basic)
            flow = FlowLayout(choices, needAni=False)
            flow.setContentsMargins(0, 0, 0, 0)
            flow.setHorizontalSpacing(10)
            flow.setVerticalSpacing(10)
            for identifier, preset in self.presets.items():
                if preset.get("group") != group:
                    continue
                button = PillPushButton(self.tra(preset["name"]), choices)
                button.setCheckable(True)
                button.setMinimumHeight(34)
                button.clicked.connect(lambda checked=False, key=identifier: self._select_preset(key))
                self.platform_buttons[identifier] = button
                flow.addWidget(button)
            layout.addWidget(choices)
        self.preset_description = CaptionLabel("", basic)
        self.preset_description.setWordWrap(True)
        self.preset_description.setTextColor("#686868", "#aaaaaa")
        layout.addWidget(self.preset_description)
        layout.addStretch(1)
        self.page_stack.addWidget(self._scroll(basic))
        self.form = MediaProviderForm(kind, self.widget, show_name=False)
        self.page_stack.addWidget(self._scroll(self.form))
        self.yesButton.setText(self.tra("下一步"))
        self.cancelButton.setText(self.tra("取消"))
        self.cancelButton.clicked.disconnect()
        self.cancelButton.clicked.connect(self._back_or_cancel)

    def _select_preset(self, identifier):
        previous_name = self.presets.get(self.selected_preset, {}).get("name", "")
        self.selected_preset = identifier
        preset = self.presets[identifier]
        if not self.name_edit.text().strip() or self.name_edit.text() == self.tra(previous_name):
            self.name_edit.setText(self.tra(preset["name"]))
        for key, button in self.platform_buttons.items():
            button.setChecked(key == identifier)
        self.preset_description.setText(self.tra(preset.get("description", "")))

    def _back_or_cancel(self):
        if self.page_stack.currentIndex() == 1:
            self.page_stack.setCurrentIndex(0)
            self.step_label.setText(self.tra("1 / 2 · 名称与平台"))
            self.yesButton.setText(self.tra("下一步"))
            self.cancelButton.setText(self.tra("取消"))
        else:
            self.reject()

    def validate(self):
        if self._committed:
            return True
        if self.page_stack.currentIndex() == 0:
            if not self.name_edit.text().strip() or self.selected_preset is None:
                self.error_toast(self.tra("请完善配置"), self.tra("请输入接口名称并选择平台。"))
                return False
            if self._loaded_preset != self.selected_preset:
                self.form.load(self.presets[self.selected_preset])
                self._loaded_preset = self.selected_preset
            self.form.name_edit.setText(self.name_edit.text())
            self.page_stack.setCurrentIndex(1)
            self.step_label.setText(self.tra("2 / 2 · 连接详情"))
            self.yesButton.setText(self.tra("添加接口"))
            self.cancelButton.setText(self.tra("上一步"))
            return False
        try:
            self.form.validate()
            data = self.form.values()
            preset = self.presets[self.selected_preset]
            data.update({key: preset[key] for key in ("group", "icon", "preset_id") if key in preset})
            self.on_confirm(data)
            self._committed = True
            return True
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
        except Exception:
            self.error_toast(self.tra("添加失败"), self.tra("接口尚未添加，请检查后端连接后重试。"))
        return False

    def prepare_to_leave(self):
        return True


class EditMediaProviderDialog(_ProviderDialog):
    def __init__(self, kind, data, parent, *, on_save):
        super().__init__("编辑接口", parent)
        self.kind = kind
        self.on_save = on_save
        self._closing = False
        self.buttonGroup.hide()
        self.form = MediaProviderForm(kind, self.widget)
        self.form.key_edit.setEchoMode(QLineEdit.Normal)
        self.form.load(data)
        self._baseline = self.form.values()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(lambda: self._flush(report_validation=False))
        self.form.changed.connect(self._schedule_save)
        self.form.editingFinished.connect(self._flush)
        self.viewLayout.addWidget(self._scroll(self.form), 1)

    def _is_dirty(self):
        return self.form.values() != self._baseline

    def _schedule_save(self):
        if self._is_dirty():
            self._save_timer.start()
        else:
            self._save_timer.stop()

    def _flush(self, *, report_validation=True):
        self._save_timer.stop()
        if not self._is_dirty():
            return True
        try:
            self.form.validate()
        except ValueError as error:
            if report_validation:
                self.error_toast(self.tra("配置无效"), self.tra(str(error)))
            return False
        values = self.form.values()
        try:
            saved = self.on_save(values)
            self.form._base_data = copy.deepcopy(saved)
            self._baseline = copy.deepcopy(values)
            return True
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
        except Exception:
            self.error_toast(self.tra("自动保存失败"), self.tra("修改尚未保存，请检查后端连接后重试。"))
        return False

    def prepare_to_leave(self):
        return self._flush()

    def done(self, result):
        if self._closing:
            return
        if self._flush():
            self._closing = True
            self.form.setEnabled(False)
            self.close_button.setEnabled(False)
            super().done(result)

    def reject(self):
        self.done(self.Rejected)

    def accept(self):
        self.done(self.Accepted)

    def closeEvent(self, event):
        # Let the guarded done() path finish the Fluent dialog's fade-out.
        # Ignoring the native close event keeps failed edits visible.
        event.ignore()
        self.reject()


class MediaProviderArgsDialog(_ProviderDialog):
    """Provider task parameters, matching the translation interface's cards."""

    def __init__(self, kind, data, parent, *, on_save):
        super().__init__("调整参数", parent)
        self.on_save = on_save
        self._saved_thread_count = normalize_media_provider(kind, data)["user_thread_counts"]
        self.widget.setFixedHeight(280)
        self.yesButton.setText(self.tra("关闭"))
        self.cancelButton.hide()
        content = QWidget(self.widget)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)

        def init(card):
            card.set_range(1, 64)
            card.spin_box.setFixedWidth(160)
            card.description_label.setWordWrap(True)
            card.set_value(self._saved_thread_count)

        self.concurrency_card = SpinCard(
            self.tra("并发任务数"),
            self.tra("每个项目同时处理的任务上限，默认 3；设为 1 时串行执行。修改在下次提交任务时生效。"),
            init=init, value_changed=self._save_concurrency,
        )
        layout.addWidget(self.concurrency_card)
        layout.addStretch(1)
        self.viewLayout.addWidget(self._scroll(content), 1)

    def _save_concurrency(self, card, value):
        try:
            self.on_save({"user_thread_counts": value})
        except Exception:
            with QSignalBlocker(card.spin_box):
                card.set_value(self._saved_thread_count)
            self.error_toast(self.tra("保存失败"), self.tra("并发任务数未保存，请检查后端连接后重试。"))
            return
        self._saved_thread_count = value

    def prepare_to_leave(self):
        self.concurrency_card.spin_box.interpretText()
        return True

    def done(self, result):
        self.prepare_to_leave()
        super().done(result)
