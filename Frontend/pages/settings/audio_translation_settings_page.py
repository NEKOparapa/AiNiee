"""Audio workflow settings, independent of transcription providers."""

from qfluentwidgets import ComboBox, FluentIcon, LineEdit, SpinBox, SwitchButton

from Frontend.core.media_task_config import (
    MEDIA_EXPORT_FORMATS, build_audio_translation_settings_update, normalize_audio_translation_settings,
    read_audio_translation_settings,
    read_video_translation_settings, build_video_translation_settings_update,
)
from Frontend.pages.settings.grouped_settings_page import GroupedSettingsPage


class AudioTranslationSettingsPage(GroupedSettingsPage):
    def __init__(self, text, parent=None, *, kind="audio"):
        self.kind = kind
        super().__init__(text, parent)

    def _build_fields(self):
        self._build_header(
            "视译设置" if self.kind == "video" else "音译设置",
            "提取视频中的音轨进行翻译，设置识别、切片与字幕导出。" if self.kind == "video" else "设置音频识别、长音频处理与字幕导出。",
        )
        recognition = self._add_section("识别参数", FluentIcon.MICROPHONE,
            "自动选择默认音轨，仅提取音频进行翻译。" if self.kind == "video" else "设置说话人识别")
        self.speaker_switch = SwitchButton(self.editor)
        recognition.add_field("说话人分离", self.speaker_switch,
                              "请求为不同说话人的内容添加区分标记。是否支持及返回效果取决于所选接口和音频语言。")

        audio = self._add_section("长音频处理", FluentIcon.SETTING, "调整长音频的切片长度；请求并发在转录接口中设置")
        self.chunk_duration_spin = SpinBox(self.editor)
        self.chunk_duration_spin.setRange(30, 290)
        self.chunk_duration_spin.setSuffix(self.tra(" 秒"))
        audio.add_field("长音频切片时长", self.chunk_duration_spin,
                        "超过 5 分钟的本地音频会按语音停顿切片，并恢复原始时间轴。此值是目标长度，实际切点会随停顿调整。")

        export = self._add_section("结果导出", FluentIcon.SHARE,
                                  "用于视频项目的字幕导出" if self.kind == "video" else "用于音频项目的字幕导出",
                                  expanded=False)
        self.export_format_combo = ComboBox(self.editor)
        for value in MEDIA_EXPORT_FORMATS[self.kind]:
            self.export_format_combo.addItem(value.upper(), userData=value)
        export.add_field("字幕格式", self.export_format_combo)
        self.export_mode_combo = ComboBox(self.editor)
        for label, value in (("双语字幕", "bilingual"), ("仅译文", "translated"), ("仅原文", "source")):
            self.export_mode_combo.addItem(self.tra(label), userData=value)
        export.add_field("字幕内容", self.export_mode_combo)
        self.export_suffix_edit = LineEdit(self.editor)
        self.export_suffix_edit.setPlaceholderText("_subtitles")
        export.add_field("输出文件名后缀", self.export_suffix_edit,
                         "添加在文件名末尾、扩展名前；留空不添加后缀。")

        self.speaker_switch.checkedChanged.connect(self._schedule_save)
        self.chunk_duration_spin.valueChanged.connect(self._schedule_save)
        self.export_format_combo.currentIndexChanged.connect(self._schedule_save)
        self.export_mode_combo.currentIndexChanged.connect(self._schedule_save)
        self.export_suffix_edit.textChanged.connect(self._schedule_save)
        self.export_suffix_edit.editingFinished.connect(self._save_settings)

    def _read_settings(self, config):
        reader = read_video_translation_settings if self.kind == "video" else read_audio_translation_settings
        return normalize_audio_translation_settings(reader(config))

    def _load_fields(self, values):
        self.speaker_switch.setChecked(values["speaker_diarization_enabled"])
        self.chunk_duration_spin.setValue(values["chunk_duration_seconds"])
        self.export_format_combo.setCurrentIndex(self.export_format_combo.findData(values["export"]["format"]))
        self.export_mode_combo.setCurrentIndex(self.export_mode_combo.findData(values["export"]["mode"]))
        self.export_suffix_edit.setText(values["export"]["suffix"])

    def _form_values(self):
        return {
            "speaker_diarization_enabled": self.speaker_switch.isChecked(),
            "chunk_duration_seconds": self.chunk_duration_spin.value(),
            "export": {
                "format": self.export_format_combo.currentData(),
                "mode": self.export_mode_combo.currentData(),
                "suffix": self.export_suffix_edit.text(),
            },
        }

    def _build_update(self, config, values):
        build = build_video_translation_settings_update if self.kind == "video" else build_audio_translation_settings_update
        return build(config, values)
