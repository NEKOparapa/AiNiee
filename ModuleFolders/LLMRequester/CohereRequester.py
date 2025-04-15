import cohere                           # pip install cohere

from Base.Base import Base

# 接口请求器
class CohereRequester(Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_cohere(self, messages, system_prompt,platform_config) -> tuple[bool, str, str, int, int]:
        try:

            api_url = platform_config.get("api_url")
            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)
            temperature = platform_config.get("temperature", 1.0)
            top_p = platform_config.get("top_p", 1.0)
            presence_penalty = platform_config.get("presence_penalty", 0)
            frequency_penalty = platform_config.get("frequency_penalty", 0)


            # 插入系统消息，与openai格式一样
            if system_prompt:
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": system_prompt
                    })


            # Cohere SDK 文档 - https://docs.cohere.com/reference/chat
            client = cohere.ClientV2(
                base_url = api_url,
                api_key = api_key,
                timeout = request_timeout,
            )

            response = client.chat(
                model = model_name,
                messages = messages,
                temperature = temperature,
                p = top_p,
                presence_penalty = presence_penalty,
                frequency_penalty = frequency_penalty,
                max_tokens = 4096,
                safety_mode = "NONE",
            )

            # 提取回复的文本内容
            response_content = response.message.content[0].text
        except Exception as e:
            self.error(f"请求任务错误 ... {e}", e if self.is_debug() else None)
            return True, None, None, None, None

        # 获取指令消耗
        try:
            prompt_tokens = int(response.usage.tokens.input_tokens)
        except Exception:
            prompt_tokens = 0

        # 获取回复消耗
        try:
            completion_tokens = int(response.usage.tokens.output_tokens)
        except Exception:
            completion_tokens = 0

        return False, "", response_content, prompt_tokens, completion_tokens
