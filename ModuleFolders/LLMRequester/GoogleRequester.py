from google import genai
from google.genai import types

from Base.Base import Base

# 接口请求器
class GoogleRequester(Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_google(self, messages, system_prompt,platform_config) -> tuple[bool, str, str, int, int]:
        try:

            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            temperature = platform_config.get("temperature", 1.0)
            top_p = platform_config.get("top_p", 1.0)

            # 重新处理openai格式的消息为google格式
            processed_messages = [{
                "role": "model" if m["role"] == "assistant" else m["role"],
                "parts": [m["content"]]
            } for m in messages if m["role"] != "system"]

            # 创建 Gemini Developer API 客户端（非 Vertex AI API）
            client = genai.Client(api_key=api_key)

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
                        types.SafetySetting(
                            category='HARM_CATEGORY_HARASSMENT',
                            threshold='BLOCK_NONE',
                        ),
                        types.SafetySetting(
                            category='HARM_CATEGORY_HATE_SPEECH',
                            threshold='BLOCK_NONE',
                        ),
                        types.SafetySetting(
                            category='HARM_CATEGORY_SEXUALLY_EXPLICIT',
                            threshold='BLOCK_NONE',
                        ),
                        types.SafetySetting(
                            category='HARM_CATEGORY_DANGEROUS_CONTENT',
                            threshold='BLOCK_NONE',
                        ),
                        types.SafetySetting(
                            category='HARM_CATEGORY_CIVIC_INTEGRITY',
                            threshold='BLOCK_NONE',
                        )
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
   