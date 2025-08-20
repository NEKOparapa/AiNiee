from google.genai import types
from google.genai.types import Content, HarmCategory, Part

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
            presence_penalty = platform_config.get("presence_penalty", 0.0)
            frequency_penalty = platform_config.get("frequency_penalty", 0.0)
            think_switch = platform_config.get("think_switch")
            thinking_budget = platform_config.get("thinking_budget")

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

            # 定义适用于文本模型的安全类别
            TEXT_HARM_CATEGORIES = [
                HarmCategory.HARM_CATEGORY_HARASSMENT,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            ]
            
            # 构建基础配置
            gen_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=65536 if model_name.startswith("gemini-2.5") else 8192,
                temperature=temperature,
                top_p=top_p,
                safety_settings=[
                    types.SafetySetting(category=category, threshold='BLOCK_NONE')
                    for category in TEXT_HARM_CATEGORIES
                ]
            )

            # 如果开启了思考模式，则添加思考配置
            if think_switch:
                gen_config.thinking_config = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=thinking_budget
                )

            # 生成文本内容
            response = client.models.generate_content(
                model=model_name,
                contents=processed_messages,
                config=gen_config,
            )

            # 初始化思考内容和回复内容
            response_think = ""
            response_content = ""

            # 根据Google API文档，思考内容和回复内容在不同的 "parts" 中
            # 遍历这些 parts 来分别提取它们
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if not part.text:
                        continue
                    # 检查 part 是否包含思考内容 (part.thought is True)
                    # 使用 hasattr 增加代码健壮性
                    if hasattr(part, 'thought') and part.thought:
                        response_think += part.text
                    else:
                        # 否则，这是常规的回复内容
                        response_content += part.text
            else:
                # 作为后备方案，如果 response.candidates[0].content.parts 不存在或为空
                # 尝试直接获取 .text 属性，这通常只包含最终回复
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

        return False, response_think, response_content, prompt_tokens, completion_tokens