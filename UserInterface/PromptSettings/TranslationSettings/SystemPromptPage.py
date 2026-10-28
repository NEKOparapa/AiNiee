from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Domain.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from UserInterface.PromptSettings.PromptLibraryPage import (
    AddEditPromptDialog, PromptCard, PromptLibraryPage,
)


class SystemPromptPage(PromptLibraryPage):
    def __init__(self, text, window):
        config = self.load_config()
        super().__init__(
            text, window,
            title=self.tra("翻译提示词"),
            description=self.tra("选择适合翻译任务的提示词，统一模型的翻译方式与输出要求。"),
            presets=self.get_default_prompt(config),
            user_prompts=config.get("translation_user_prompt_data", []),
            selected_id=config.get("translation_prompt_selection", {}).get("last_selected_id"),
            selection_key="translation_prompt_selection",
            user_data_key="translation_user_prompt_data",
        )

    def get_default_prompt(self, config):
        return [
            {"id": preset, "name": self.tra(name), "summary": self.tra(summary),
             "content": PromptBuilder.get_system_default(config, preset), "type": "system"}
            for preset, name, summary in (
                (PromptBuilderEnum.COMMON, "通用", "适用于日常文本翻译"),
                (PromptBuilderEnum.COT, "思维链", "先分析，再组织译文"),
                (PromptBuilderEnum.LOCAL, "本地模型", "适配本地部署的模型"),
            )
        ]
