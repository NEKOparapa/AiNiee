import cohere                           # pip install cohere
import anthropic                        # pip install anthropic
import google.generativeai as genai     # pip install google-generativeai
from openai import OpenAI               # pip install openai


from Base.Base import Base
from Base.PluginManager import PluginManager
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig

# 接口请求器
class TranslatorRequester(Base):


    def __init__(self, config: TranslatorConfig, plugin_manager: PluginManager) -> None:
        super().__init__()

        # 初始化
        self.config = config
        self.plugin_manager = plugin_manager

    # 分发请求
    def sent_request(self, messages: list[dict], system_prompt: str,platform_config) -> tuple[bool, str, int, int]:
        # 获取平台参数
        target_platform = platform_config.get("target_platform")
        api_format = platform_config.get("api_format")

        # 发起请求
        if target_platform == "sakura":
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_sakura(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "LocalLLM":
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_LocalLLM(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "cohere":
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_cohere(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "google":
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_google(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "anthropic" or (target_platform.startswith("custom_platform_") and api_format == "Anthropic"):
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_anthropic(
                messages,
                system_prompt,
                platform_config,
            )
        else:
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_openai(
                messages,
                system_prompt,
                platform_config,
            )

        return skip, response_think, response_content, prompt_tokens, completion_tokens


    # 发起请求
    def request_sakura(self, messages, system_prompt, platform_config) -> tuple[bool, str, int, int]:
        try:

            api_url = platform_config.get("api_url")
            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout")
            temperature = platform_config.get("temperature")
            top_p = platform_config.get("top_p")
            frequency_penalty = platform_config.get("frequency_penalty")

            # 插入系统消息
            if system_prompt:
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": system_prompt
                    })

            client = OpenAI(
                base_url = api_url,
                api_key = api_key,
            )

            response = client.chat.completions.create(
                model = model_name,
                messages = messages,
                top_p = top_p,
                temperature = temperature,
                frequency_penalty = frequency_penalty,
                timeout = request_timeout,
                max_tokens = max(512, self.config.tokens_limit) if self.config.tokens_limit_switch == True else 512,
                extra_query = {
                    "do_sample": True,
                    "num_beams": 1,
                    "repetition_penalty": 1.0
                },
            )

            # 提取回复的文本内容
            response_content = response.choices[0].message.content
        except Exception as e:
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)
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

        # 将回复内容包装进可变数据容器里，使之可以被修改，并自动传回
        response_content_dict = {"0":response_content}

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "sakura_reply_processed",
            self.config,
            response_content_dict
        )

        # 插件事件过后，恢复字符串类型
        response_content = response_content_dict["0"]

        # Sakura 返回的内容多行文本，将其转换为 textarea标签包裹，方便提取
        response_content = "<textarea>\n" + response_content + "\n</textarea>"

        return False, "", response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_LocalLLM(self, messages, system_prompt,platform_config) -> tuple[bool, str, int, int]:
        try:

            api_url = platform_config.get("api_url")
            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout")
            temperature = platform_config.get("temperature")
            top_p = platform_config.get("top_p")
            frequency_penalty = platform_config.get("frequency_penalty")

            # 插入系统消息
            if system_prompt:
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": system_prompt
                    })


            client = OpenAI(
                base_url = api_url,
                api_key = api_key,
            )

            response = client.chat.completions.create(
                model = model_name,
                messages = messages,
                top_p = top_p,
                temperature = temperature,
                frequency_penalty = frequency_penalty,
                timeout = request_timeout,
            )


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
                except Exception:
                    response_think = ""
                response_content = message.content

        except Exception as e:
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)
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

        #print("模型回复内容:\n" + response_content)


        # 将回复内容包装进可变数据容器里，使之可以被修改，并自动传回
        response_content_dict = {"0":response_content}

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "reply_processed",
            self.config,
            response_content_dict
        )

        # 插件事件过后，恢复字符串类型
        response_content = response_content_dict["0"]

        # 提取多标签情况的翻译文本,整合在一个标签里面，方便后面再次提取
        #response_content = TranslatorRequester.extract_span_content_regex(self,response_content)



        return False, response_think, response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_cohere(self, messages, system_prompt,platform_config) -> tuple[bool, str, int, int]:
        try:

            api_url = platform_config.get("api_url")
            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout")
            temperature = platform_config.get("temperature")
            top_p = platform_config.get("top_p")
            presence_penalty = platform_config.get("presence_penalty")
            frequency_penalty = platform_config.get("frequency_penalty")


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
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)
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

        # 将回复内容包装进可变数据容器里，使之可以被修改，并自动传回
        response_content_dict = {"0":response_content}

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "reply_processed",
            self.config,
            response_content_dict
        )

        # 插件事件过后，恢复字符串类型
        response_content = response_content_dict["0"]

        return False, "", response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_google(self, messages, system_prompt,platform_config) -> tuple[bool, str, int, int]:
        try:

            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            temperature = platform_config.get("temperature")
            top_p = platform_config.get("top_p")

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
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)
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

        # 将回复内容包装进可变数据容器里，使之可以被修改，并自动传回
        response_content_dict = {"0":response_content}

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "reply_processed",
            self.config,
            response_content_dict
        )

        # 插件事件过后，恢复字符串类型
        response_content = response_content_dict["0"]

        return False, "", response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_anthropic(self, messages, system_prompt,platform_config) -> tuple[bool, str, int, int]:
        try:

            api_url = platform_config.get("api_url")
            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout")
            temperature = platform_config.get("temperature")
            top_p = platform_config.get("top_p")


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
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)
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

        # 将回复内容包装进可变数据容器里，使之可以被修改，并自动传回
        response_content_dict = {"0":response_content}

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "reply_processed",
            self.config,
            response_content_dict
        )

        # 插件事件过后，恢复字符串类型
        response_content = response_content_dict["0"]

        return False, "", response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_openai(self, messages, system_prompt,platform_config) -> tuple[bool, str, int, int]:
        try:
            # 获取具体配置
            api_url = platform_config.get("api_url")
            api_key = platform_config.get("api_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout")
            temperature = platform_config.get("temperature")
            top_p = platform_config.get("top_p")
            presence_penalty = platform_config.get("presence_penalty")
            frequency_penalty = platform_config.get("frequency_penalty")
            extra_body = platform_config.get("extra_body","{}")

            # 插入系统消息
            if system_prompt:
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": system_prompt
                    })


            client = OpenAI(
                base_url = api_url,
                api_key= api_key,
            )

            # 针对ds-r模型的特殊处理，因为该模型不支持模型预输入回复
            if model_name in {"deepseek-reasoner", "deepseek-r1", "DeepSeek-R1"}:
                # 检查一下最后的消息是否用户消息，以免误删。(用户使用了推理模型卻不切换为推理模型提示词的情况)
                if isinstance(messages[-1], dict) and messages[-1].get('role') != 'user':
                    messages = messages[:-1]  # 移除最后一个元素


            # 部分平台和模型不接受frequency_penalty参数
            if presence_penalty == 0 and frequency_penalty == 0:
                response = client.chat.completions.create(
                    extra_body = extra_body,
                    model = model_name,
                    messages = messages,
                    temperature = temperature,
                    top_p = top_p,
                    timeout = request_timeout,
                    stream = False
                )

            else:
                response = client.chat.completions.create(
                    extra_body = extra_body,
                    model = model_name,
                    messages = messages,
                    temperature = temperature,
                    top_p = top_p,
                    presence_penalty = presence_penalty,
                    frequency_penalty = frequency_penalty,
                    timeout = request_timeout,
                    stream = False
                )

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
                except Exception:
                    response_think = ""
                response_content = message.content

        except Exception as e:
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)
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

        # 将回复内容包装进可变数据容器里，使之可以被修改，并自动传回
        response_content_dict = {"0":response_content}

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "reply_processed",
            self.config,
            response_content_dict
        )

        # 插件事件过后，恢复字符串类型
        response_content = response_content_dict["0"]

        return False, response_think, response_content, prompt_tokens, completion_tokens