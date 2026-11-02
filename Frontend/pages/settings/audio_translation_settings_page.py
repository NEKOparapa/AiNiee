"""Audio workflow settings, independent of transcription providers."""

from qfluentwidgets import ComboBox, FluentIcon, SpinBox, SwitchButton

from Frontend.core.media_task_config import (
    MEDIA_EXPORT_FORMATS, build_audio_translation_settings_update, normalize_audio_translation_settings,
    read_audio_translation_settings,
)
from Frontend.pages.settings.media_settings_page import MediaSettingsPage


class AudioTranslationSettingsPage(MediaSettingsPage):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)

    def _build_fields(self):
        recognition = self._add_section("识别参数", FluentIcon.MICROPHONE, "设置说话人识别")
        self.speaker_switch = SwitchButton(self.editor)
        recognition.add_field("说话人分离", self.speaker_switch,
                              "请求为不同说话人的内容添加区分标记。是否支持及返回效果取决于所选接口和音频语言。")

        audio = self._add_section("长音频处理", FluentIcon.SETTING, "调整长音频的切片长度与请求并发")
        self.chunk_duration_spin = SpinBox(self.editor)
        self.chunk_duration_spin.setRange(30, 290)
        self.chunk_duration_spin.setSuffix(self.tra(" 秒"))
        audio.add_field("长音频切片时长", self.chunk_duration_spin,
                        "超过 5 分钟的本地音频会按语音停顿切片，并恢复原始时间轴。此值是目标长度，实际切点会随停顿调整。")
        self.chunk_concurrency_spin = SpinBox(self.editor)
        self.chunk_concurrency_spin.setRange(1, 8)
        audio.add_field("切片并发数", self.chunk_concurrency_spin,
                        "同时发送的转录请求数。遇到服务限流时可降低此值；已完成的切片可随中间模型继续使用。")

        export = self._add_section("导出设置", FluentIcon.SHARE, "用于音频项目的字幕导出")
        self.export_format_combo = ComboBox(self.editor)
        for value in MEDIA_EXPORT_FORMATS["audio"]:
            self.export_format_combo.addItem(value.upper(), userData=value)
        export.add_field("字幕格式", self.export_format_combo)
        self.export_mode_combo = ComboBox(self.editor)
        for label, value in (("双语字幕", "bilingual"), ("仅译文", "translated"), ("仅原文", "source")):
            self.export_mode_combo.addItem(self.tra(label), userData=value)
        export.add_field("字幕内容", self.export_mode_combo)

        self.speaker_switch.checkedChanged.connect(self._schedule_save)
        self.chunk_duration_spin.valueChanged.connect(self._schedule_save)
        self.chunk_concurrency_spin.valueChanged.connect(self._schedule_save)
        self.export_format_combo.currentIndexChanged.connect(self._schedule_save)
        self.export_mode_combo.currentIndexChanged.connect(self._schedule_save)

    def _read_settings(self, config):
        return normalize_audio_translation_settings(read_audio_translation_settings(config))

    def _load_fields(self, values):
        self.speaker_switch.setChecked(values["speaker_diarization_enabled"])
        self.chunk_duration_spin.setValue(values["chunk_duration_seconds"])
        self.chunk_concurrency_spin.setValue(values["chunk_concurrency"])
        self.export_format_combo.setCurrentIndex(self.export_format_combo.findData(values["export"]["format"]))
        self.export_mode_combo.setCurrentIndex(self.export_mode_combo.findData(values["export"]["mode"]))

    def _form_values(self):
        return {
            "speaker_diarization_enabled": self.speaker_switch.isChecked(),
            "chunk_duration_seconds": self.chunk_duration_spin.value(),
            "chunk_concurrency": self.chunk_concurrency_spin.value(),
            "export": {
                "format": self.export_format_combo.currentData(),
                "mode": self.export_mode_combo.currentData(),
            },
        }

    def _build_update(self, config, values):
        return build_audio_translation_settings_update(config, values)
