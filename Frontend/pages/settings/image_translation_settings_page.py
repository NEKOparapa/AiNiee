"""Settings for single-step image translation and export."""

from qfluentwidgets import ComboBox, FluentIcon, LineEdit, SwitchButton

from Frontend.core.media_task_config import (
    MEDIA_EXPORT_FORMATS, build_image_translation_settings_update, normalize_image_translation_settings,
    read_image_translation_settings,
)
from Frontend.pages.settings.media_settings_page import MediaSettingsPage


class ImageTranslationSettingsPage(MediaSettingsPage):
    def __init__(self, text, parent=None):
        self._active_format = ""
        super().__init__(text, parent)

    def _build_fields(self):
        generation = self._add_section("生成参数", FluentIcon.SETTING, "原图与翻译要求一次提交，直接生成译图")
        self.size_edit = LineEdit(self.editor)
        self.size_edit.setPlaceholderText("auto / 1536*1024 / 2K")
        generation.add_field("输出尺寸", self.size_edit,
                             "auto 由接口自动选择。Gemini 支持 1K、2K、4K；Seedream 支持 1K、1.5K、2K；其他尺寸范围由模型决定。")
        self.prompt_extend_switch = SwitchButton(self.editor)
        generation.add_field("自动改写提示词", self.prompt_extend_switch,
                             "仅用于百炼图像接口；Seedream 使用标准优化，Gemini 按原提示词生成。")
        export = self._add_section("导出设置", FluentIcon.SHARE, "用于图片项目的译图导出")
        self.export_format_combo = ComboBox(self.editor)
        for value in MEDIA_EXPORT_FORMATS["image"]:
            self.export_format_combo.addItem(value.upper(), userData=value)
        export.add_field("图片格式", self.export_format_combo)
        self.prompt_extend_switch.checkedChanged.connect(self._schedule_save)
        self.size_edit.textChanged.connect(self._schedule_save)
        self.size_edit.editingFinished.connect(self._save_settings)
        self.export_format_combo.currentIndexChanged.connect(self._schedule_save)

    def _read_settings(self, config):
        provider = config.get("image_generation_platforms", {}).get(config.get("active_image_generation_platform"), {})
        self._active_format = provider.get("api_format", "")
        return normalize_image_translation_settings(read_image_translation_settings(config))

    def _load_fields(self, values):
        generation = values["generation"]
        self.size_edit.setText(generation["size"])
        self.size_edit.setPlaceholderText("auto / 1K / 2K / 4K" if self._active_format == "Gemini" else "auto / 1536*1024 / 2K")
        self.prompt_extend_switch.setChecked(generation["prompt_extend"])
        self.prompt_extend_switch.setEnabled(self._active_format == "DashScope")
        self.export_format_combo.setCurrentIndex(self.export_format_combo.findData(values["export"]["format"]))

    def _form_values(self):
        return {
            "generation": {"size": self.size_edit.text(), "prompt_extend": self.prompt_extend_switch.isChecked()},
            "export": {"format": self.export_format_combo.currentData()},
        }

    def _build_update(self, config, values):
        return build_image_translation_settings_update(config, values)
