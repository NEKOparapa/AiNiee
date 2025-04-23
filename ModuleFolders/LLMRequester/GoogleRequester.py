from google.genai import types
from google.genai.types import Content, Part

from Base.Base import Base
from ModuleFolders.LLMRequester.LLMClientFactory import LLMClientFactory


# 接口请求器
class GoogleRequester(Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_google(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            model_name = platform_config.get("model_name")
            temperature = platform_config.get("temperature", 1.0)
            top_p = platform_config.get("top_p", 1.0)

            # 重新处理openai格式的消息为google格式
            processed_messages = [
                Content(
                    role="model" if m["role"] == "assistant" else m["role"],
                    parts=[Part.from_text(text=m["content"])]
                )
                for m in messages if m["role"] != "system"
            ]

            # 创建 Gemini Developer API 客户端（非 Vertex AI API）
            client = LLMClientFactory().get_google_client(platform_config)

            # 生成文本内容
            response = client.models.generate_content(
                model=model_name,
                contents=processed_messages,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=32768 if model_name.startswith("gemini-2.5") else 8192,
                    temperature=temperature,
                    top_p=top_p,
                    safety_settings=[
                        types.SafetySetting(category=f'HARM_CATEGORY_{cat}', threshold='BLOCK_NONE')
                        for cat in
                        ["HARASSMENT", "HATE_SPEECH", "SEXUALLY_EXPLICIT", "DANGEROUS_CONTENT", "CIVIC_INTEGRITY"]
                    ]
                ),
            )

            # 提取回复的文本内容
            response_content = response.text
        except Exception as e:
            self.error(f"请求任务错误 ... {e}", e if self.is_debug() else None)
            return True, None, None, None, None

        # 获取指令消耗
        try:
            prompt_tokens = int(response.usage_metadata.prompt_token_count)
        except Exception:
            prompt_tokens = 0

        # 获取回复消耗
        try:
            completion_tokens = int(response.usage_metadata.candidates_token_count)
        except Exception:
            completion_tokens = 0

        return False, "", response_content, prompt_tokens, completion_tokens
