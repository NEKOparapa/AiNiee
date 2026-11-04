"""Text task settings grouped by workflow, with editors hosted in the same route."""

import copy

from PyQt5.QtCore import QEvent, QFileInfo
from qfluentwidgets import (
    CaptionLabel, ComboBox, FluentIcon as FI, LineEdit, PushButton, SpinBox, SwitchButton,
)

from Frontend.pages.settings.grouped_settings_page import GroupedSettingsPage, SettingsWorkspacePage
from Frontend.platform.file_dialogs import get_existing_directory
from Frontend.services.backend_paths import auto_output_dir
from Frontend.services.editor import PromptBuilderExtraction
from Frontend.services.protocol import PromptBuilderEnum


class TextSettingsOverview(GroupedSettingsPage):
    def __init__(self, stage, parent):
        self.stage = stage
        self.controls = {}
        self.prompt_summaries = {}
        self.defaults = {}
        # Keep the existing default sections and wire format for old projects/configs.
        for name in ("TaskSettingsPage", "ExtractionSettingsPage", "TranslationSettingsPage", "OutputSettingsPage"):
            self.defaults.update(self.get_default_section(name))
        super().__init__(stage + "_settings_overview", parent)

    def _build_fields(self):
        title, description = (
            ("提取设置", "识别原文中的角色、术语与禁翻项，并统一提取结果。")
            if self.stage == "extraction" else
            ("翻译设置", "设置文本翻译的任务处理、提示词、质量检查与结果导出。")
        )
        self._build_header(title, description)
        task = self._add_section("任务执行", FI.SETTING)
        if self.stage == "extraction":
            self._spin(task, "extract_task_token_limit", "每批 Token 数", "提取任务专用，决定每次提交给模型的原文大小。", minimum=1)
        else:
            self._combo(task, "lines_limit_switch", "任务切分模式", [("Token模式", False), ("行数模式", True)])
            self.token_row = self._spin(task, "tokens_limit", "每批 Token 数", "按 Token 数切分待翻译文本。")
            self.line_row = self._spin(task, "lines_limit", "每批行数", "按行数切分待翻译文本。")
            self.controls["lines_limit_switch"].currentIndexChanged.connect(self._update_mode)
        if self.stage == "extraction":
            rules = self._add_section("提取规则", FI.FILTER)
            self._switch(rules, "auto_extract_non_translate_switch", "自动提取禁翻词条", "提取后可在结果中审查和筛选，确认需要保留的内容。")
            self._switch(rules, "extract_short_name_merge_switch", "自动合并长短名称", "例如将“亚瑟”和“亚瑟王”归并为同一角色。")
            prompts = self._add_section("提取提示词", FI.BOOK_SHELF)
            self._prompt(prompts, "basic", "基础提示")
            self._prompt(prompts, "judgment", "裁定提示")
        else:
            self._spin(task, "round_limit", "最大翻译轮次", "未完成的条目在下一轮重试，直到完成或达到上限。")
            processing = self._add_section("文本处理", FI.FILTER)
            self._switch(processing, "auto_process_text_code_segment", "自动预处理文本", "根据正则库与禁翻表保护非翻译内容，翻译后还原。")
            self._switch(processing, "language_filter_switch", "自动过滤其他语言文本", "启用后，将在翻译前，自动过滤掉与设置的原文语言不一致的文本，不参与翻译")
            self._switch(processing, "code_filter_switch", "自动过滤代码文本", "启用后，将在翻译前，自动过滤掉代码文本，不参与翻译（仅作用于Mtool项目）")
            prompts = self._add_section("提示与上下文", FI.BOOK_SHELF, expanded=False)
            self._spin(prompts, "pre_line_counts", "参考上文行数", "随翻译任务提供的前文数量；0 表示不提供。")
            self._switch(prompts, "few_shot_and_example_switch", "动态示例与预回复", "根据任务内容构建翻译示例和预回复；不支持本地接口。")
            self._prompt(prompts, "translation", "基础提示")
            self._prompt(prompts, "guidance", "翻译指导", "管理翻译指导")
            checks = self._add_section("检查与修复", FI.ACCEPT, expanded=False)
            self._switch(checks, "response_check_switch.return_to_original_text_check", "返回原文检查", "检查译文是否与原文完全相同。")
            self._switch(checks, "response_check_switch.residual_original_text_check", "残留原文检查", "检查译文中是否残留应当翻译的原文。")
            self._switch(checks, "response_check_switch.newline_character_count_check", "换行符数检查", "检查原文与译文的换行符数量是否一致。")
            self._switch(checks, "text_symbol_repair_switch", "自动修复标点符号", "启用后，将在翻译任务中根据原文恢复译文中改变的标点符号和文本符号，适合日语翻译流程。")
            output = self._add_section("结果导出", FI.SHARE, expanded=False)
            self._switch(output, "auto_set_output_path", "自动设置输出文件夹", "使用输入目录旁的 AiNieeOutput 文件夹。")
            self.controls["auto_set_output_path"].checkedChanged.connect(self._refresh_output_display)
            self.output_button = PushButton(FI.FOLDER_ADD, self.tra("选择文件夹"), self)
            self.output_button.clicked.connect(self._choose_output)
            self.output_row = output.add_field("翻译输出文件夹", self.output_button, "当前输出文件夹为")
            self.output_row.setAcceptDrops(True)
            self.output_row.installEventFilter(self)
            self.output_description = self.output_row.findChild(CaptionLabel)
            self._output_path = ""
            suffix = LineEdit(self)
            suffix.setPlaceholderText("_translated")
            self.controls["output_filename_suffix"] = suffix
            suffix.textChanged.connect(self._schedule_save)
            output.add_field("输出文件名后缀", suffix)
            self._combo(output, "bilingual_text_order", "双语文件文本顺序", [("原文在上", "source_first"), ("译文在上", "translation_first")], "仅用于 TXT 和 EPUB 项目。")
            self._switch(output, "keep_original_encoding", "保持输入输出文件编码一致", "字符不兼容时使用 UTF-8；关闭后始终使用 UTF-8。")

    def _spin(self, section, key, title, description="", minimum=0):
        control = SpinBox(self)
        control.setRange(minimum, 9999999)
        self.controls[key] = control
        control.valueChanged.connect(self._schedule_save)
        return section.add_field(title, control, description)

    def _switch(self, section, key, title, description=""):
        control = SwitchButton(self)
        self.controls[key] = control
        control.checkedChanged.connect(self._schedule_save)
        return section.add_field(title, control, description)

    def _combo(self, section, key, title, choices, description=""):
        control = ComboBox(self)
        for label, value in choices:
            control.addItem(self.tra(label), userData=value)
        self.controls[key] = control
        control.currentIndexChanged.connect(self._schedule_save)
        return section.add_field(title, control, description)

    def _prompt(self, section, key, title, action="管理提示词"):
        button = PushButton(FI.EDIT, self.tra(action), self)
        button.clicked.connect(lambda: self.editorRequested.emit(key))
        row = section.add_field(title, button, " ")
        self.prompt_summaries[key] = row.findChild(CaptionLabel)

    def _read_settings(self, config):
        values = copy.deepcopy(self.defaults)
        values.update(config)
        return values

    def _load_fields(self, values):
        for key, control in self.controls.items():
            if "." in key:
                group, field = key.split(".")
                value = values.get(group, {}).get(field, self.defaults.get(group, {}).get(field, True))
            else:
                value = values.get(key)
            if isinstance(control, SwitchButton):
                control.setChecked(bool(value))
            elif isinstance(control, SpinBox):
                control.setValue(int(value or 0))
            elif isinstance(control, ComboBox):
                control.setCurrentIndex(max(0, control.findData(value)))
            else:
                control.setText(str(value or ""))
        if self.stage == "translation":
            self._output_path = values.get("label_output_path", "")
            self._input_path = values.get("label_input_path", "")
            self._update_mode()
            self._refresh_output_display()
        for key, caption in self.prompt_summaries.items():
            if key == "guidance":
                enabled = [self.tra(title) for prefix, title in (("characterization", "角色介绍"), ("world_building", "背景设定"), ("writing_style", "翻译风格"), ("translation_example", "翻译示例")) if values.get(prefix + "_switch")]
                caption.setText(" · ".join(enabled) if enabled else self.tra("角色介绍、背景设定、翻译风格与翻译示例"))
                continue
            if key == "translation":
                selection, users = "translation_prompt_selection", "translation_user_prompt_data"
                preset_names = {PromptBuilderEnum.COMMON: "通用", PromptBuilderEnum.COT: "思维链", PromptBuilderEnum.LOCAL: "本地模型"}
            else:
                stage = PromptBuilderExtraction.BASIC if key == "basic" else PromptBuilderExtraction.JUDGMENT
                settings = PromptBuilderExtraction.STAGES[stage]
                selection, users = settings["selection_key"], settings["user_data_key"]
                preset_names = {settings["preset_id"]: "通用"}
            selected = values.get(selection, {}).get("last_selected_id")
            name = next((p["name"] for p in values.get(users, []) if p.get("id") == selected), self.tra(preset_names.get(selected, "通用")))
            caption.setText(self.tra("当前使用：{name}").format(name=name))

    def _form_values(self):
        values = {}
        for key, control in self.controls.items():
            if isinstance(control, SwitchButton):
                value = control.isChecked()
            elif isinstance(control, SpinBox):
                value = control.value()
            elif isinstance(control, ComboBox):
                value = control.currentData()
            else:
                value = control.text().strip()
            values[key] = value
        if self.stage == "translation":
            values["label_output_path"] = self._output_path
        return values

    def _build_update(self, current, values):
        patch = {}
        for key, value in values.items():
            if self._baseline is not None and value == self._baseline.get(key):
                continue
            if "." in key:
                group, field = key.split(".")
                patch.setdefault(group, copy.deepcopy(current.get(group, {})))[field] = value
            else:
                patch[key] = value
        if "lines_limit_switch" in patch:
            patch["tokens_limit_switch"] = not patch["lines_limit_switch"]
        return patch

    def _update_mode(self, *_):
        lines = self.controls["lines_limit_switch"].currentData()
        self.line_row.setVisible(bool(lines))
        self.token_row.setVisible(not lines)

    def _refresh_output_display(self, *_):
        automatic = self.controls["auto_set_output_path"].isChecked()
        path = getattr(self, "_output_path", "")
        source = getattr(self, "_input_path", "")
        if automatic and source:
            path = auto_output_dir(source)
        self.output_description.setText(path or self.tra("选择输入文件后自动确定"))
        self.output_button.setEnabled(not automatic)

    def _choose_output(self):
        path = get_existing_directory(self, self.tra("选择文件夹"), self._output_path)
        if path:
            self._set_output_path(path)

    def _set_output_path(self, path):
        self._output_path = path.strip()
        self._refresh_output_display()
        self._schedule_save()

    def eventFilter(self, watched, event):
        if watched is getattr(self, "output_row", None) and event.type() in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop):
            path = next((url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile() and QFileInfo(url.toLocalFile()).isDir()), None)
            if path and not self.controls["auto_set_output_path"].isChecked():
                if event.type() == QEvent.Drop:
                    self._set_output_path(path)
                event.acceptProposedAction()
            else:
                event.ignore()
            return True
        return super().eventFilter(watched, event)


class TextSettingsPage(SettingsWorkspacePage):
    """Only the owning settings page is registered with the main navigation."""

    def __init__(self, text, window, *, stage):
        self.stage = stage
        super().__init__(text, window,
                         title="提取设置" if stage == "extraction" else "翻译设置",
                         overview_factory=lambda parent: TextSettingsOverview(stage, parent))

    def _editor_title(self, key):
        return "管理翻译指导" if key == "guidance" else "管理提示词"

    def _create_editor(self, key):
        # Lazy construction keeps startup light and reads the latest prompt data.
        if key == "guidance":
            from Frontend.pages.prompts.translation.guidance_page import TranslationGuidancePage
            return TranslationGuidancePage(self)
        if key == "translation":
            from Frontend.pages.prompts.translation.system_prompt_page import SystemPromptPage
            return SystemPromptPage("text_translation_prompts", self)
        from Frontend.pages.prompts.extraction.extraction_prompt_page import ExtractionPromptPage
        stage = PromptBuilderExtraction.BASIC if key == "basic" else PromptBuilderExtraction.JUDGMENT
        return ExtractionPromptPage("text_extraction_" + key, self, stage)

