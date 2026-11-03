"""The image translation instruction library, independent of text prompts."""
import copy

from Frontend.components.toast import ToastMixin
from Frontend.pages.prompts.prompt_library_page import (
    AddEditPromptDialog, PromptLibraryPage, secondary_label,
)


DEFAULT_PROMPT_ID = "image_translation_default"
SELECTION_KEY = "image_translation_prompt_selection"
USER_DATA_KEY = "image_translation_user_prompt_data"


def validate_image_prompt(data):
    """Validate user entries before sending the complete library to the backend."""
    if not isinstance(data, dict):
        raise ValueError("图片翻译提示词必须是对象。")
    for field, label, maximum in (("id", "提示词 ID", 128), ("name", "提示词名称", 100),
                                   ("content", "提示词内容", 10000)):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
            raise ValueError(f"{label}必须为 1 至 {maximum} 字且不含空字符的文本。")
    if data["id"] == DEFAULT_PROMPT_ID:
        raise ValueError("自定义提示词不能使用系统预设的 ID。")
    if data.get("type") != "user":
        raise ValueError("图片自定义提示词的类型必须为 user。")
    return {key: data[key] for key in ("id", "name", "content", "type")}


def read_user_prompts(config):
    values = config.get(USER_DATA_KEY, [])
    if not isinstance(values, list):
        raise ValueError("图片自定义提示词库必须是列表。")
    prompts = [validate_image_prompt(entry) for entry in values]
    if len({entry["id"] for entry in prompts}) != len(prompts):
        raise ValueError("图片自定义提示词的 ID 不能重复。")
    return prompts


class ImagePromptDialog(AddEditPromptDialog):
    def __init__(self, prompt_data=None, parent=None, *, initial_content=""):
        super().__init__(prompt_data, parent)
        self.validation_label = secondary_label("", self)
        self.validation_label.setWordWrap(True)
        self.viewLayout.addWidget(self.validation_label)
        self.content_edit.setPlaceholderText(self.tra("填写完整的图片翻译指令，最多 10000 字。"))
        self.name_edit.setMaxLength(100)
        if prompt_data is None:
            self.content_edit.setPlainText(initial_content)
        self.update_form_state()

    def _validation_error(self):
        name, content = self.name_edit.text().strip(), self.content_edit.toPlainText()
        if not name or not content.strip():
            return self.tra("请填写提示词名称和内容。")
        if len(name) > 100 or "\x00" in name:
            return self.tra("提示词名称最多 100 字且不能包含空字符。")
        if len(content) > 10000 or "\x00" in content:
            return self.tra("提示词内容最多 10000 字且不能包含空字符。")
        return ""

    def update_form_state(self):
        super().update_form_state()
        error = self._validation_error()
        self.yesButton.setEnabled(not error)
        if hasattr(self, "validation_label"):
            self.validation_label.setText(error)
            self.validation_label.setVisible(bool(error))

    def validate(self):
        return not self._validation_error()


class ImageTranslationPromptPage(PromptLibraryPage, ToastMixin):
    def __init__(self, text, window=None):
        self._loading = True
        self._ready = False
        config = self.load_config()
        preset = {
            "id": DEFAULT_PROMPT_ID,
            "name": self.tra("单步图片翻译"),
            "summary": self.tra("翻译原文、原位回填并保留画面"),
            "content": self.get_prompt_presets("image_translation")[DEFAULT_PROMPT_ID],
            "type": "system",
        }
        super().__init__(
            text, window,
            title=self.tra("图片翻译提示词"),
            description=self.tra("选择或自定义图片翻译指令，控制译文、文字排版和原画保留方式。"),
            presets=[preset], user_prompts=read_user_prompts(config),
            selected_id=config.get(SELECTION_KEY, {}).get("last_selected_id", DEFAULT_PROMPT_ID),
            selection_key=SELECTION_KEY, user_data_key=USER_DATA_KEY,
            guidance=self.tra("自定义提示词替换默认翻译指令，选择后自动保存，下次生成译图时生效。原图和原文、译文语言由程序提供，无需填写占位符。"),
        )
        self._loading = False
        self._ready = True

    def _apply_config(self, config):
        prompts = read_user_prompts(config)
        selected = config.get(SELECTION_KEY, {}).get("last_selected_id", DEFAULT_PROMPT_ID)
        self._loading = True
        try:
            self.user_prompts = prompts
            self.update_prompt_cards(selected)
        finally:
            self._loading = False

    def showEvent(self, event):
        super().showEvent(event)
        if self._ready:
            try:
                self._apply_config(self.load_config())
            except Exception:
                self.error_toast(self.tra("读取失败"), self.tra("无法读取图片翻译提示词，请检查后端连接后重试。"))

    def display_prompt_details(self, prompt_data, *, persist=True):
        if self._loading or not persist:
            return super().display_prompt_details(prompt_data, persist=False)
        return self._commit_change(selected_id=prompt_data["id"])

    def _commit_change(self, *, selected_id=None, edit=None, delete_id=None):
        """Commit against the latest config before displaying a new active prompt."""
        try:
            edit = validate_image_prompt(edit) if edit is not None else None

            def update(config):
                prompts = read_user_prompts(config)
                active = selected_id or config.get(SELECTION_KEY, {}).get("last_selected_id", DEFAULT_PROMPT_ID)
                if edit is not None:
                    index = next((i for i, item in enumerate(prompts) if item["id"] == edit["id"]), None)
                    if index is None:
                        prompts.append(copy.deepcopy(edit))
                    else:
                        prompts[index] = copy.deepcopy(edit)
                    active = edit["id"]
                if delete_id is not None:
                    prompts = [item for item in prompts if item["id"] != delete_id]
                    if active == delete_id:
                        active = DEFAULT_PROMPT_ID
                chosen = (self.default_prompt[0] if active == DEFAULT_PROMPT_ID else
                          next((item for item in prompts if item["id"] == active), None))
                if chosen is None:
                    raise ValueError("所选提示词已不存在，请重新打开页面后选择。")
                config[SELECTION_KEY] = {"last_selected_id": active, "prompt_content": chosen["content"]}
                config[USER_DATA_KEY] = prompts

            config = self.update_config(update)
            self._apply_config(config)
            return True
        except ValueError as error:
            self.error_toast(self.tra("配置无效"), self.tra(str(error)))
        except Exception:
            self.error_toast(self.tra("保存失败"), self.tra("修改尚未应用，请检查后端连接后重试。"))
        return False

    def open_add_prompt_dialog(self, prompt_to_edit=None):
        if isinstance(prompt_to_edit, bool):
            prompt_to_edit = None
        if prompt_to_edit is not None and prompt_to_edit.get("type") != "user":
            return
        dialog = ImagePromptDialog(prompt_to_edit, self, initial_content=self.default_prompt[0]["content"])
        try:
            while dialog.exec_():
                data = dialog.get_data()
                if data and self._commit_change(edit=data):
                    self.search_edit.clear()
                    self.scroll_area.ensureWidgetVisible(self.selected_prompt_card)
                    break
                # Keep the user's text in the editor when the server rejects a save.
                dialog.validation_label.setText(self.tra("保存失败，内容仍保留在此，请检查后端连接后重试。"))
                dialog.validation_label.show()
        finally:
            dialog.deleteLater()

    def delete_user_prompt(self, prompt_id):
        if any(item["id"] == prompt_id for item in self.user_prompts):
            return self._commit_change(delete_id=prompt_id)
        return False
