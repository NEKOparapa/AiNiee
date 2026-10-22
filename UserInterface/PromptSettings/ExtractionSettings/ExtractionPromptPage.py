from ModuleFolders.Domain.PromptBuilder.PromptBuilderExtraction import PromptBuilderExtraction
from UserInterface.PromptSettings.PromptLibraryPage import PromptLibraryPage


class ExtractionPromptPage(PromptLibraryPage):
    DESCRIPTIONS = {
        PromptBuilderExtraction.BASIC: "用于第一阶段：从原文提取角色、术语和禁翻项。",
        PromptBuilderExtraction.JUDGMENT: "用于第二阶段：合并候选结果，裁定角色和术语分类。",
    }

    def __init__(self, text, window, stage):
        self.stage = stage
        self.settings = PromptBuilderExtraction.STAGES[stage]
        config = self.load_config()
        self.preset_prompt = {
            "id": self.settings["preset_id"],
            "name": self.tra("通用"),
            "summary": self.tra("识别角色、术语与禁翻项" if stage == PromptBuilderExtraction.BASIC else "合并候选并裁定分类"),
            "content": PromptBuilderExtraction.get_system_default(stage),
            "type": "system",
        }
        selected = PromptBuilderExtraction.get_selected_user_prompt(config, stage) or self.preset_prompt
        title = "提取提示词 · 基础提示" if stage == PromptBuilderExtraction.BASIC else "提取提示词 · 裁定提示"
        super().__init__(
            text, window,
            title=self.tra(title),
            description=self.tra(self.DESCRIPTIONS[stage]),
            presets=[self.preset_prompt],
            user_prompts=PromptBuilderExtraction.get_user_prompts(config, stage),
            selected_id=selected["id"],
            selection_key=self.settings["selection_key"],
            user_data_key=self.settings["user_data_key"],
            guidance=self.tra("仅配置系统提示词，请保留预设中的 JSON 输出字段。示例、输入数据和目标语言要求由程序生成；修改将在下次提取任务生效。"),
        )
