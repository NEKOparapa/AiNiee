"""Image workflow settings shared across OCR and image-generation providers."""

from qfluentwidgets import ComboBox, FluentIcon, LineEdit, SwitchButton

from Frontend.core.media_task_config import (
    MEDIA_EXPORT_FORMATS, build_image_translation_settings_update, normalize_image_translation_settings,
    read_image_translation_settings,
)
from Frontend.pages.settings.media_settings_page import MediaSettingsPage


class ImageTranslationSettingsPage(MediaSettingsPage):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)

    def _build_fields(self):
        recognition = self._add_section("识别参数", FluentIcon.DOCUMENT, "用于OCR翻译流程")
        self.reading_combo = ComboBox(self.editor)
        for label, value in (("自动判断", "auto"), ("从左向右", "ltr"), ("漫画从右向左", "manga_rtl")):
            self.reading_combo.addItem(self.tra(label), userData=value)
        recognition.add_field("阅读顺序", self.reading_combo,
                              "日文漫画可选择从右向左；文字本身的横排或竖排由识别结果决定。")
        self.group_switch = SwitchButton(self.editor)
        recognition.add_field("合并相邻文字行", self.group_switch,
                              "默认关闭。开启后尝试把同一区域中的文字行组合为翻译条目；复杂漫画建议先检查分组结果。")
        self.refine_switch = SwitchButton(self.editor)
        recognition.add_field("复核气泡原文", self.refine_switch,
                              "需同时开启“合并相邻文字行”。对明确封闭的气泡额外调用百炼多语言识别，改善日文识别；会增加请求次数和费用，低可信结果保留原文。")

        generation = self._add_section("生成参数", FluentIcon.SETTING, "用于整图生成翻译流程")
        self.size_edit = LineEdit(self.editor)
        self.size_edit.setPlaceholderText("auto / 1536*1024 / 2K")
        generation.add_field("输出尺寸", self.size_edit,
                             "填写 auto 自动匹配尺寸，或填写 宽*高。Seedream 另支持 1K、1.5K、2K，尺寸范围由模型决定。")
        self.prompt_extend_switch = SwitchButton(self.editor)
        generation.add_field("自动改写提示词", self.prompt_extend_switch,
                             "用于百炼图像接口；Seedream 使用模型自带的标准提示词优化。")

        export = self._add_section("导出设置", FluentIcon.SHARE, "用于图片项目的译图导出")
        self.export_format_combo = ComboBox(self.editor)
        for value in MEDIA_EXPORT_FORMATS["image"]:
            self.export_format_combo.addItem(value.upper(), userData=value)
        export.add_field("图片格式", self.export_format_combo)

        self.reading_combo.currentIndexChanged.connect(self._schedule_save)
        self.group_switch.checkedChanged.connect(self._on_group_changed)
        self.refine_switch.checkedChanged.connect(self._schedule_save)
        self.prompt_extend_switch.checkedChanged.connect(self._schedule_save)
        self.size_edit.textChanged.connect(self._schedule_save)
        self.size_edit.editingFinished.connect(self._save_settings)
        self.export_format_combo.currentIndexChanged.connect(self._schedule_save)

    def _on_group_changed(self, enabled):
        if self._loading:
            return
        self.refine_switch.setEnabled(enabled)
        if not enabled:
            blocked = self.refine_switch.blockSignals(True)
            try:
                self.refine_switch.setChecked(False)
            finally:
                self.refine_switch.blockSignals(blocked)
        self._schedule_save()

    def _read_settings(self, config):
        return normalize_image_translation_settings(read_image_translation_settings(config))

    def _load_fields(self, values):
        ocr, generation = values["ocr"], values["generation"]
        self.reading_combo.setCurrentIndex(self.reading_combo.findData(ocr["reading_order"]))
        self.group_switch.setChecked(ocr["group_lines"])
        self.refine_switch.setChecked(ocr["refine_text"])
        self.refine_switch.setEnabled(ocr["group_lines"])
        self.size_edit.setText(generation["size"])
        self.prompt_extend_switch.setChecked(generation["prompt_extend"])
        self.export_format_combo.setCurrentIndex(self.export_format_combo.findData(values["export"]["format"]))

    def _form_values(self):
        return {
            "ocr": {
                "reading_order": self.reading_combo.currentData(),
                "group_lines": self.group_switch.isChecked(),
                "refine_text": self.refine_switch.isChecked(),
            },
            "generation": {
                "size": self.size_edit.text(),
                "prompt_extend": self.prompt_extend_switch.isChecked(),
            },
            "export": {"format": self.export_format_combo.currentData()},
        }

    def _build_update(self, config, values):
        return build_image_translation_settings_update(config, values)
