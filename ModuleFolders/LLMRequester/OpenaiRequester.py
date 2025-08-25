from Base.Base import Base
from ModuleFolders.LLMRequester.LLMClientFactory import LLMClientFactory


# 接口请求器
class OpenaiRequester(Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_openai(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            # 获取具体配置
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)
            temperature = platform_config.get("temperature", 1.0)
            top_p = platform_config.get("top_p", 1.0)
            presence_penalty = platform_config.get("presence_penalty", 0)
            frequency_penalty = platform_config.get("frequency_penalty", 0)
            extra_body = platform_config.get("extra_body", "{}")
            think_switch = platform_config.get("think_switch")
            think_depth = platform_config.get("think_depth")

            # 插入系统消息
            if system_prompt:
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": system_prompt
                    })

            # 从工厂获取客户端
            client = LLMClientFactory().get_openai_client(platform_config)

            # 针对ds模型的特殊处理，因为该模型不支持模型预输入回复
            if 'deepseek' in model_name.lower():
                # 检查一下最后的消息是否用户消息，以免误删。(用户使用了推理模型卻不切换为推理模型提示词的情况)
                if messages and isinstance(messages[-1], dict) and messages[-1].get('role') != 'user':
                    messages = messages[:-1]  # 移除最后一个元素


            # 参数基础配置
            base_params = {
                "extra_body": extra_body,
                "model": model_name,
                "messages": messages,
                "timeout": request_timeout,
                "stream": False
            }

            # 按需添加参数
            if temperature != 1:
                base_params.update({
                    "temperature": temperature,
                })

            if top_p != 1:
                base_params.update({
                    "top_p": top_p,
                })

            if presence_penalty != 0:
                base_params.update({
                    "presence_penalty": presence_penalty,
                })

            if frequency_penalty != 0:
                base_params.update({
                    "frequency_penalty": frequency_penalty
                })


            # 开启思考开关时添加参数
            if think_switch:
                base_params.update({
                    "reasoning_effort": think_depth
                })


            # 发起请求
            response = client.chat.completions.create(**base_params)


            # 提取回复内容
            message = response.choices[0].message

            # 自适应提取推理过程
            if "</think>" in message.content:
                splited = message.content.split("</think>")
                response_think = splited[0].removeprefix("<think>").replace("\n\n", "\n")
                response_content = splited[-1]
            else:
                try:
                    response_think = message.reasoning_content
                    if not response_think:
                        response_think = ""
                except Exception:
                    response_think = ""
                response_content = message.content

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

        return False, response_think, response_content, prompt_tokens, completion_tokens
