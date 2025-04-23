from Base.Base import Base
from ModuleFolders.LLMRequester.LLMClientFactory import LLMClientFactory


# 接口请求器
class SakuraRequester(Base):
    def __init__(self):
        pass

    # 发起请求
    def request_sakura(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)
            temperature = platform_config.get("temperature", 0.1)
            top_p = platform_config.get("top_p", 0.3)
            frequency_penalty = platform_config.get("frequency_penalty", 0)

            # 插入系统消息
            if system_prompt:
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": system_prompt
                    })

            # 从工厂获取客户端
            client = LLMClientFactory().get_openai_client_sakura(platform_config)

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                top_p=top_p,
                temperature=temperature,
                frequency_penalty=frequency_penalty,
                timeout=request_timeout,
                max_tokens=512,
                extra_query={
                    "do_sample": True,
                    "num_beams": 1,
                    "repetition_penalty": 1.0
                },
            )

            # 提取回复的文本内容
            response_content = response.choices[0].message.content
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

        # Sakura 返回的内容多行文本，将其转换为 textarea标签包裹，方便提取
        response_content = "<textarea>\n" + response_content + "\n</textarea>"

        return False, "", response_content, prompt_tokens, completion_tokens
