from ModuleFolders.Base.Base import Base
from ModuleFolders.Infrastructure.LLMRequester.LLMClientFactory import LLMClientFactory
from ModuleFolders.Infrastructure.LLMRequester.ModelConfigHelper import ModelConfigHelper


# 接口请求器
class AnthropicRequester(Base):
    def __init__(self) -> None:
        pass

    def _calculate_budget_tokens(self, think_depth: str, max_tokens: int) -> int:
        """
        根据思考深度档位计算 budget_tokens
        参考比例：low ~10%, medium ~40%, high ~70%
        Anthropic 要求 budget_tokens 最小值为 1024
        """
        ratio_map = {
            "low": 0.1,
            "medium": 0.4,
            "high": 0.7,
        }
        ratio = ratio_map.get(think_depth, 0.5)  # 默认 medium
        budget = int(max_tokens * ratio)
        # Anthropic 的 budget_tokens 最小值是 1024
        return max(1024, budget)

    def request_anthropic(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)
            temperature = platform_config.get("temperature", 1.0)
            top_p = platform_config.get("top_p", 0.95)
            think_switch = platform_config.get("think_switch")
            think_depth = platform_config.get("think_depth")

            max_tokens = ModelConfigHelper.get_claude_max_output_tokens(model_name)

            # 参数基础配置
            base_params = {
                "model": model_name,
                "system": system_prompt,
                "messages": messages,
                "timeout": request_timeout,
                "max_tokens": max_tokens,
            }

            # 添加思考模式配置
            if think_switch:
                budget_tokens = self._calculate_budget_tokens(think_depth, max_tokens)
                base_params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": budget_tokens
                }
                # 启用 extended thinking 时，temperature 必须为 1
                base_params["temperature"] = 1.0
            else:
                base_params["temperature"] = temperature
            # top_p参数设置
            base_params["top_p"] = top_p

            # 从工厂获取客户端
            client = LLMClientFactory().get_anthropic_client(platform_config)
            # 发送请求
            response = client.messages.create(**base_params)

            # 提取回复的文本内容和思考内容
            response_think = ""
            response_content = ""
            for block in response.content:
                if hasattr(block, "type"):
                    if block.type == "thinking":
                        response_think = block.thinking
                    elif block.type == "text":
                        response_content = block.text

        except Exception as e:
            self.error(f"请求任务错误 ... {e}", e if self.is_debug() else None)
            return True, None, None, None, None

        # 获取指令消耗（Anthropic 使用 input_tokens）
        try:
            prompt_tokens = int(response.usage.input_tokens)
        except Exception:
            prompt_tokens = 0

        # 获取回复消耗（Anthropic 使用 output_tokens）
        try:
            completion_tokens = int(response.usage.output_tokens)
        except Exception:
            completion_tokens = 0

        return False, response_think, response_content, prompt_tokens, completion_tokens
