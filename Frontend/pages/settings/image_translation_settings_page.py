"""Settings for single-step image translation and export."""

from qfluentwidgets import CaptionLabel, ComboBox, FluentIcon, LineEdit, PushButton

from Frontend.core.media_task_config import (
    MEDIA_EXPORT_FORMATS, build_image_translation_settings_update, normalize_image_translation_settings,
    read_image_translation_settings,
)
from Frontend.pages.settings.grouped_settings_page import GroupedSettingsPage, SettingsWorkspacePage


class ImageTranslationSettingsOverview(GroupedSettingsPage):
    def __init__(self, text, parent=None):
        self._active_format = ""
        super().__init__(text, parent)

    def _build_fields(self):
        self._build_header("图译设置", "设置译图生成、翻译提示词与结果导出。")
        generation = self._add_section("生成参数", FluentIcon.SETTING, "原图与翻译要求一次提交，直接生成译图")
        self.size_edit = LineEdit(self.editor)
        self.size_edit.setPlaceholderText("auto / 1536*1024 / 2K")
        generation.add_field("输出尺寸", self.size_edit,
                             "auto 由接口自动选择。OpenAI 支持 1024x1024、1536x1024、1024x1536；Gemini 支持 1K、2K、4K；Seedream 支持 1K、1.5K、2K。")
        prompts = self._add_section("翻译提示词", FluentIcon.BOOK_SHELF)
        self.prompt_button = PushButton(FluentIcon.EDIT, self.tra("管理提示词"), self.editor)
        self.prompt_button.clicked.connect(lambda: self.editorRequested.emit("prompts"))
        row = prompts.add_field("图片翻译提示词", self.prompt_button, " ")
        self.prompt_summary = row.findChild(CaptionLabel)
        export = self._add_section("结果导出", FluentIcon.SHARE, "用于图片项目的译图导出", expanded=False)
        self.export_format_combo = ComboBox(self.editor)
        for value in MEDIA_EXPORT_FORMATS["image"]:
            self.export_format_combo.addItem(value.upper(), userData=value)
        export.add_field("图片格式", self.export_format_combo)
        self.export_suffix_edit = LineEdit(self.editor)
        self.export_suffix_edit.setPlaceholderText("_translated")
        export.add_field("输出文件名后缀", self.export_suffix_edit,
                         "添加在文件名末尾、扩展名前；留空不添加后缀。")
        self.size_edit.textChanged.connect(self._schedule_save)
        self.size_edit.editingFinished.connect(self._save_settings)
        self.export_format_combo.currentIndexChanged.connect(self._schedule_save)
        self.export_suffix_edit.textChanged.connect(self._schedule_save)
        self.export_suffix_edit.editingFinished.connect(self._save_settings)

    def _read_settings(self, config):
        provider = config.get("image_generation_platforms", {}).get(config.get("active_image_generation_platform"), {})
        self._active_format = provider.get("api_format", "")
        selected = config.get("image_translation_prompt_selection", {}).get("last_selected_id")
        self._prompt_name = next((p["name"] for p in config.get("image_translation_user_prompt_data", [])
                                  if p.get("id") == selected), self.tra("单步图片翻译"))
        return normalize_image_translation_settings(read_image_translation_settings(config))

    def _load_fields(self, values):
        generation = values["generation"]
        self.size_edit.setText(generation["size"])
        self.size_edit.setPlaceholderText("auto / 1K / 2K / 4K" if self._active_format == "Gemini" else
                                         "auto / 1024x1024 / 1536x1024 / 1024x1536" if self._active_format == "OpenAI" else
                                         "auto / 1536*1024 / 2K")
        self.export_format_combo.setCurrentIndex(self.export_format_combo.findData(values["export"]["format"]))
        self.export_suffix_edit.setText(values["export"]["suffix"])
        self.prompt_summary.setText(self.tra("当前使用：{name}").format(name=self._prompt_name))

    def _form_values(self):
        return {
            "generation": {"size": self.size_edit.text()},
            "export": {"format": self.export_format_combo.currentData(), "suffix": self.export_suffix_edit.text()},
        }

    def _build_update(self, config, values):
        return build_image_translation_settings_update(config, values)


class ImageTranslationSettingsPage(SettingsWorkspacePage):
    def __init__(self, text, parent=None):
        super().__init__(text, parent, title="图译设置",
                         overview_factory=lambda owner: ImageTranslationSettingsOverview("image_settings_overview", owner))

    def _create_editor(self, key):
        if key != "prompts":
            raise ValueError(key)
        from Frontend.pages.prompts.image_translation_prompt_page import ImageTranslationPromptPage
        return ImageTranslationPromptPage("image_translation_prompts", self)
