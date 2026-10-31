from Frontend.services.protocol import PromptBuilderEnum
from Frontend.pages.prompts.prompt_library_page import (
    AddEditPromptDialog, PromptCard, PromptLibraryPage,
)


class PolishingSystemPromptPage(PromptLibraryPage):
    def __init__(self, text, window):
        config = self.load_config()
        super().__init__(
            text, window,
            title=self.tra("润色提示词"),
            description=self.tra("设定润色的表达风格，让译文更自然、流畅。"),
            presets=self.get_default_prompt(config),
            user_prompts=config.get("polishing_user_prompt_data", []),
            selected_id=config.get("polishing_prompt_selection", {}).get("last_selected_id"),
            selection_key="polishing_prompt_selection",
            user_data_key="polishing_user_prompt_data",
        )

    def get_default_prompt(self, config):
        return [{
            "id": PromptBuilderEnum.POLISH_COMMON,
            "name": self.tra("通用"),
            "summary": self.tra("改善译文的表达与行文"),
            "content": self.get_prompt_presets("polishing")[str(PromptBuilderEnum.POLISH_COMMON)],
            "type": "system",
        }]
