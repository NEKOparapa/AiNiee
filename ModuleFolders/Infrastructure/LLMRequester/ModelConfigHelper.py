import re


class ModelConfigHelper:
    """模型配置辅助类，用于获取不同模型的输出限制等配置"""

    # Claude 模型输出限制映射
    CLAUDE_OUTPUT_LIMITS = {
        # Claude 4.5 系列
        "claude-sonnet-4-5": 64000,
        "claude-haiku-4-5": 64000,
        "claude-opus-4-5": 64000,
        # Claude 4.x 系列
        "claude-opus-4-1": 32000,
        "claude-sonnet-4": 64000,
        "claude-opus-4": 32000,
        # Claude 3.x 系列
        "claude-3-7-sonnet": 64000,
        "claude-3-5-haiku": 8000,
        "claude-3-haiku": 4000,
        "claude-3-opus": 4000,
        "claude-3-sonnet": 4000,
    }
    CLAUDE_DEFAULT_LIMIT = 4000

    # Google 模型输出限制映射
    GOOGLE_OUTPUT_LIMITS = {
        "gemini-3-pro": 65536,
        "gemini-2.5-flash": 65536,
        "gemini-2.5-flash-lite": 65536,
        "gemini-2.5-pro": 65536,
        "gemini-2.0-flash": 8192,
        "gemini-2.0-flash-lite": 8192,
    }
    GOOGLE_DEFAULT_LIMIT = 8192

    @staticmethod
    def _extract_claude_version_info(model_name: str) -> tuple[float, str]:
        """从 Claude 模型名称中提取版本号和模型类型

        返回: (版本号, 模型类型)
        """
        # 提取模型类型
        model_type = ""
        if "haiku" in model_name.lower():
            model_type = "haiku"
        elif "sonnet" in model_name.lower():
            model_type = "sonnet"
        elif "opus" in model_name.lower():
            model_type = "opus"

        # 提取版本号
        version_match = re.search(r'claude-(?:\w+-)?([\d-]+)', model_name)
        if version_match:
            version_str = version_match.group(1).replace('-', '.')
            version_parts = version_str.split('.')[:2]
            try:
                if len(version_parts) == 1:
                    version = float(version_parts[0])
                else:
                    version = float(f"{version_parts[0]}.{version_parts[1]}")
                return version, model_type
            except ValueError:
                pass

        return 0.0, model_type

    @staticmethod
    def _extract_google_version(model_name: str) -> float:
        """从 Google 模型名称中提取版本号"""
        match = re.search(r'gemini-(\d+(?:\.\d+)?)', model_name)
        if match:
            return float(match.group(1))
        return 0.0

    @classmethod
    def is_gemini_3_or_newer(cls, model_name: str) -> bool:
        """检测是否为 Gemini 3.x 或更新版本"""
        version = cls._extract_google_version(model_name)
        return version >= 3.0

    @classmethod
    def get_thinking_level_options(cls, model_name: str) -> list[str]:
        """获取模型支持的 thinking_level 选项

        Gemini 3 Pro: low, high
        Gemini 3 Flash: minimal, low, medium, high
        """
        if "flash" in model_name.lower():
            return ["minimal", "low", "medium", "high"]
        else:  # Pro 模型
            return ["low", "high"]

    @classmethod
    def get_claude_max_output_tokens(cls, model_name: str) -> int:
        """获取 Claude 模型的最大输出 token 限制"""
        # 优先检查已知模型
        for known_model, limit in sorted(cls.CLAUDE_OUTPUT_LIMITS.items(),
                                         key=lambda x: len(x[0]),
                                         reverse=True):
            if known_model in model_name:
                return limit

        # 根据版本号和类型推断
        version, model_type = cls._extract_claude_version_info(model_name)

        if version > 0 and model_type:
            # Claude 4.5+: 统一 64K
            if version >= 4.5:
                return 64000

            # Claude 4.x
            elif version >= 4.0:
                if model_type == "opus":
                    return 32000
                else:
                    return 64000

            # Claude 3.x
            elif version >= 3.0:
                if version >= 3.5:
                    if model_type == "sonnet":
                        return 64000
                    elif model_type == "haiku":
                        return 8000
                return 4000

        # 使用默认值
        return cls.CLAUDE_DEFAULT_LIMIT

    @classmethod
    def get_google_max_output_tokens(cls, model_name: str) -> int:
        """获取 Google 模型的最大输出 token 限制"""
        # 优先检查已知模型
        for known_model, limit in sorted(cls.GOOGLE_OUTPUT_LIMITS.items(),
                                         key=lambda x: len(x[0]),
                                         reverse=True):
            if known_model in model_name:
                return limit

        # 根据版本号推断
        version = cls._extract_google_version(model_name)
        if version > 0:
            if version >= 2.5:
                return 65536
            else:
                return 8192

        # 使用默认值
        return cls.GOOGLE_DEFAULT_LIMIT
