import re


class ModelConfigHelper:
    """集中维护需要由多个请求器和界面共享的模型配置规则。"""

    CLAUDE_5_MODEL_IDS = (
        "claude-fable-5",
        "claude-mythos-5",
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-haiku-5",
    )
    CLAUDE_5_MAX_OUTPUT_TOKENS = 128000

    @classmethod
    def get_claude_max_output_tokens(cls, model_name: str) -> int:
        normalized_name = str(model_name or "").lower()
        if not any(model in normalized_name for model in cls.CLAUDE_5_MODEL_IDS):
            raise ValueError("Anthropic 接口仅支持 Claude 5 系列模型")
        return cls.CLAUDE_5_MAX_OUTPUT_TOKENS

    # 支持服务端拒答回退（fallbacks）的型号，仅 Anthropic 官方接口可用。
    CLAUDE_FALLBACK_MODEL_IDS = (
        "claude-fable-5",
        "claude-opus-5",
        "claude-sonnet-5-5",
    )
    CLAUDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"

    @classmethod
    def get_claude_fallback_params(cls, model_name: str, api_url: str | None) -> dict:
        """被安全分类器拒答（stop_reason=refusal）时，让服务端按拒答类别自动换模型重试。

        只对 api.anthropic.com 开启：第三方中转与 Bedrock 不认这个参数。
        """
        normalized_name = str(model_name or "").lower()
        host = str(api_url or "https://api.anthropic.com").lower()
        if "api.anthropic.com" not in host:
            return {}
        if not any(model in normalized_name for model in cls.CLAUDE_FALLBACK_MODEL_IDS):
            return {}
        return {"betas": [cls.CLAUDE_FALLBACK_BETA], "fallbacks": "default"}

    @staticmethod
    def build_claude_system(system_prompt: str, cache_prefix_len: int | None):
        """把系统提示词拆成两段：固定前缀加缓存断点，其后按批次变化的部分（术语表等）不缓存。"""
        if not system_prompt or not cache_prefix_len or cache_prefix_len > len(system_prompt):
            return system_prompt
        prefix, rest = system_prompt[:cache_prefix_len], system_prompt[cache_prefix_len:]
        if not prefix.strip():
            return system_prompt
        blocks = [{"type": "text", "text": prefix, "cache_control": {"type": "ephemeral"}}]
        if rest.strip():
            blocks.append({"type": "text", "text": rest})
        return blocks

    @staticmethod
    def get_claude_thinking_off_params(model_name: str) -> dict:
        """关闭思考开关时要并入请求的参数，各型号写法不同。

        - Fable / Mythos：思考常开，不传 thinking。
        - Opus 5.5：不能关思考（disabled 返回 400），不传 thinking，把 effort 降到 low。
        - Sonnet 5.5：disabled 返回 400，用 between_tools 关思考。
        - 其余（Opus 5、Sonnet 5、Haiku 5.5）：thinking disabled。
        """
        normalized_name = str(model_name or "").lower()
        if any(model in normalized_name for model in ("claude-fable-5", "claude-mythos-5")):
            return {}
        if "claude-opus-5-5" in normalized_name:
            return {"output_config": {"effort": "low"}}
        if "claude-sonnet-5-5" in normalized_name:
            return {"thinking": {"type": "between_tools"}}
        return {"thinking": {"type": "disabled"}}

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
