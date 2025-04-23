from Base.Base import Base
from ModuleFolders.LLMRequester.LLMClientFactory import LLMClientFactory


# 接口请求器
class CohereRequester(Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_cohere(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            model_name = platform_config.get("model_name")
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
            # 从工厂获取客户端
            client = LLMClientFactory().get_cohere_client(platform_config)

            response = client.chat(
                model=model_name,
                messages=messages,
                temperature=temperature,
                p=top_p,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                max_tokens=4096,
                safety_mode="NONE",
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
