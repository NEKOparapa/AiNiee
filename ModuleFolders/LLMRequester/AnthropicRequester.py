from Base.Base import Base
from ModuleFolders.LLMRequester.LLMClientFactory import LLMClientFactory


def is_claude3_model(model_name):
    """判断是否为Claude 3系列模型"""
    return any(variant in model_name for variant in ["3-haiku", "3-opus", "3-sonnet"])


# 接口请求器
class AnthropicRequester(Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_anthropic(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)
            temperature = platform_config.get("temperature", 1.0)
            top_p = platform_config.get("top_p", 1.0)

            # 从工厂获取客户端
            client = LLMClientFactory().get_anthropic_client(platform_config)

            response = client.messages.create(
                model=model_name,
                system=system_prompt,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                timeout=request_timeout,
                max_tokens=4096 if is_claude3_model(model_name) else 8192,
            )

            # 提取回复的文本内容
            response_content = response.content[0].text
        except Exception as e:
            self.error(f"请求任务错误 ... {e}", e if self.is_debug() else None)
            return True, None, None, None, None

        # 获取指令消耗
        try:
            prompt_tokens = int(response.usage.prompt_tokens)
        except Exception:
            prompt_tokens = 0

        # 获取回复消耗
        try:
            completion_tokens = int(response.usage.completion_tokens)
        except Exception:
            completion_tokens = 0

        return False, "", response_content, prompt_tokens, completion_tokens
