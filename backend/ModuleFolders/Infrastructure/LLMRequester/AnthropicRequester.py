from ModuleFolders.Base.Base import Base
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.LLMRequester.LLMClientFactory import LLMClientFactory
from ModuleFolders.Infrastructure.LLMRequester.ModelConfigHelper import ModelConfigHelper


# 接口请求器
class AnthropicRequester(LogMixin, Base):
    def __init__(self) -> None:
        pass

    def request_anthropic(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)
            think_switch = platform_config.get("think_switch")
            think_depth = platform_config.get("think_depth") or "medium"

            max_tokens = ModelConfigHelper.get_claude_max_output_tokens(model_name)

            # Claude 5 不接受 assistant 末尾预填充。
            if (
                messages
                and isinstance(messages[-1], dict)
                and messages[-1].get("role") == "assistant"
            ):
                messages = messages[:-1]

            # 参数基础配置
            base_params = {
                "model": model_name,
                "system": system_prompt,
                "messages": messages,
                "timeout": request_timeout,
                "max_tokens": max_tokens,
            }

            # Claude 5 统一使用 adaptive thinking + output_config.effort，且不发送采样温度。
            if think_switch:
                base_params["thinking"] = {
                    "type": "adaptive",
                    "display": "summarized",
                }
                base_params["output_config"] = {
                    "effort": think_depth
                    if think_depth in {"low", "medium", "high", "xhigh", "max"}
                    else "medium"
                }
            elif not ModelConfigHelper.is_claude_always_thinking_model(model_name):
                base_params["thinking"] = {"type": "disabled"}

            # 从工厂获取客户端
            client = LLMClientFactory().get_anthropic_client(platform_config)
            # 发送请求
            response = client.messages.create(**base_params)

            # 提取回复的文本内容和思考内容
            thinking_parts = []
            content_parts = []
            for block in response.content:
                if hasattr(block, "type"):
                    if block.type == "thinking":
                        thinking_text = getattr(block, "thinking", "")
                        if thinking_text:
                            thinking_parts.append(thinking_text)
                    elif block.type == "text":
                        content_parts.append(block.text)

            response_think = "".join(thinking_parts)
            response_content = "".join(content_parts)

        except Exception as e:
            if Base.work_status == Base.STATUS.STOPING:
                return True, None, None, None, None
            self.error(f"请求任务错误 ... {e}", e)
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
