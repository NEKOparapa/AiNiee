import google.generativeai as genai     # pip install google-generativeai

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


            # Gemini SDK 文档 - https://ai.google.dev/api?hl=zh-cn&lang=python
            genai.configure(
                api_key = api_key,
                transport = "rest",
            )

            model = genai.GenerativeModel(
                model_name = model_name,
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ],
                system_instruction = system_prompt,
            )

            # 提取回复的文本内容
            response = model.generate_content(
                processed_messages,
                generation_config = {
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_output_tokens": 7096,
                },
            )
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
   