import anthropic                        # pip install anthropic

from Base.Base import Base

# 接口请求器
class AnthropicRequester(Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_anthropic(self, messages, system_prompt,platform_config) -> tuple[bool, str, str, int, int]:
        try:

            api_url = platform_config.get("api_url")
            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)
            temperature = platform_config.get("temperature", 1.0)
            top_p = platform_config.get("top_p", 1.0)


            client = anthropic.Anthropic(
                base_url = api_url,
                api_key = api_key,
            )

            response = client.messages.create(
                model = model_name,
                system = system_prompt,
                messages = messages,
                temperature = temperature,
                top_p = top_p,
                timeout = request_timeout,
                max_tokens = 4096,
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
