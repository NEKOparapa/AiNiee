from functools import lru_cache

from ModuleFolders.Config.FilePathConfig import prompt_path
from ModuleFolders.Domain.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum


class PromptBuilderExtraction:
    BASIC = "basic"
    JUDGMENT = "judgment"
    STAGES = {
        BASIC: {
            "selection_key": "extract_prompt_selection",
            "user_data_key": "extract_user_prompt_data",
            "preset_id": PromptBuilderEnum.EXTRACT_COMMON,
            "file_name": "basic_system_zh.txt",
        },
        JUDGMENT: {
            "selection_key": "extract_judgment_prompt_selection",
            "user_data_key": "extract_judgment_user_prompt_data",
            "preset_id": PromptBuilderEnum.EXTRACT_JUDGMENT,
            "file_name": "judgment_system_zh.txt",
        },
    }

    @classmethod
    @lru_cache(maxsize=2)
    def get_system_default(cls, stage: str) -> str:
        file_name = cls.STAGES[stage]["file_name"]
        return prompt_path("Extract", file_name).read_text(encoding="utf-8").strip()

    @staticmethod
    def _config_value(config, key: str, default=None):
        # 页面使用配置字典，任务使用启动时载入的 TaskConfig 快照。
        if isinstance(config, dict):
            return config.get(key, default)
        return getattr(config, key, default)

    @classmethod
    def get_user_prompts(cls, config, stage: str) -> list[dict]:
        prompts = cls._config_value(config, cls.STAGES[stage]["user_data_key"], [])
        if not isinstance(prompts, list):
            return []
        return [
            dict(prompt)
            for prompt in prompts
            if isinstance(prompt, dict)
            and prompt.get("type") == "user"
            and all(
                isinstance(prompt.get(key), str) and prompt[key].strip()
                for key in ("id", "name", "content")
            )
        ]

    @classmethod
    def get_selected_user_prompt(cls, config, stage: str) -> dict | None:
        selection = cls._config_value(config, cls.STAGES[stage]["selection_key"], {})
        if not isinstance(selection, dict):
            return None
        content = selection.get("prompt_content")
        if not isinstance(content, str) or not content.strip():
            return None
        return next(
            (
                prompt for prompt in cls.get_user_prompts(config, stage)
                if prompt["id"] == selection.get("last_selected_id")
            ),
            None,
        )

    @classmethod
    def build_system(cls, config, stage: str) -> str:
        # 已删除或无效的卡片不能仅凭残留的 prompt_content 继续生效。
        if cls.get_selected_user_prompt(config, stage) is not None:
            selection = cls._config_value(config, cls.STAGES[stage]["selection_key"])
            return selection["prompt_content"]
        return cls.get_system_default(stage)
