"""Migration of retired built-in translation prompt selections."""

from ModuleFolders.Config.FilePathConfig import prompt_path
from ModuleFolders.Domain.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum


class TranslationPromptConfigHelper:
    @staticmethod
    def normalize_config(config: dict) -> bool:
        selection = config.get("translation_prompt_selection")
        if not isinstance(selection, dict):
            return False

        previous_id = selection.get("last_selected_id")
        preset_id = PromptBuilderEnum.normalize_translation_preset(previous_id)
        if preset_id == previous_id:
            return False

        language = config.get("target_language", "chinese_simplified")
        suffix = "zh" if language in ("chinese_simplified", "chinese_traditional") else "en"
        content = prompt_path("Translate", f"common_system_{suffix}.txt").read_text(encoding="utf-8").strip()
        config["translation_prompt_selection"] = {
            **selection,
            "last_selected_id": preset_id,
            "prompt_content": content,
        }
        return True
