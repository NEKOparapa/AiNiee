"""The image translation instruction library, independent of text prompts."""

from Frontend.pages.prompts.editable_prompt_library_page import EditablePromptLibraryPage


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


class ImageTranslationPromptPage(EditablePromptLibraryPage):
    def __init__(self, text, window=None):
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
        self.selected_prompt_content_text.setPlaceholderText(self.tra("填写完整的图片翻译指令，最多 10000 字。"))

    def _read_user_prompts(self, config):
        return read_user_prompts(config)

    def _validate_user_prompt(self, prompt):
        if len(prompt["content"]) > 10000:
            raise ValueError("提示词内容最多 10000 字且不能包含空字符。")
        return validate_image_prompt(prompt)
