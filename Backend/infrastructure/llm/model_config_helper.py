import re


class ModelConfigHelper:
    """集中维护需要由多个请求器和界面共享的模型配置规则。"""

    CLAUDE_5_MODEL_IDS = (
        "claude-fable-5",
        "claude-mythos-5",
        "claude-opus-5",
        "claude-sonnet-5",
    )
    CLAUDE_5_MAX_OUTPUT_TOKENS = 128000

    @classmethod
    def get_claude_max_output_tokens(cls, model_name: str) -> int:
        normalized_name = str(model_name or "").lower()
        if not any(model in normalized_name for model in cls.CLAUDE_5_MODEL_IDS):
            raise ValueError("Anthropic 接口仅支持 Claude 5 系列模型")
        return cls.CLAUDE_5_MAX_OUTPUT_TOKENS

    @staticmethod
    def is_claude_always_thinking_model(model_name: str) -> bool:
        normalized_name = str(model_name or "").lower()
        return any(
            model in normalized_name
            for model in ("claude-fable-5", "claude-mythos-5")
        )

    @staticmethod
    def _extract_google_version(model_name: str) -> float:
        match = re.search(r"gemini-(\d+(?:\.\d+)?)", str(model_name or "").lower())
        return float(match.group(1)) if match else 0.0

    @classmethod
    def is_gemini_3_or_newer(cls, model_name: str) -> bool:
        return cls._extract_google_version(model_name) >= 3.0

    @classmethod
    def get_google_max_output_tokens(cls, model_name: str) -> int:
        return 65536 if cls._extract_google_version(model_name) >= 2.5 else 8192

    @staticmethod
    def get_thinking_level_options(model_name: str) -> list[str]:
        normalized_name = str(model_name or "").lower()
        if "gemini-3.7-flash" in normalized_name:
            return ["low", "medium", "high"]
        if "flash" in normalized_name:
            return ["minimal", "low", "medium", "high"]
        if "gemini-3.1-pro" in normalized_name:
            return ["low", "medium", "high"]
        return ["low", "high"]
