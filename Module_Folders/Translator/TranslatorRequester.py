import re
import threading

import cohere                           # pip install cohere
import anthropic                        # pip install anthropic
import google.generativeai as genai     # pip install google-generativeai
from openai import OpenAI               # pip install openai

import rapidjson as json

from Base.Base import Base
from Base.PluginManager import PluginManager
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig
from Module_Folders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum


# 接口请求器
class TranslatorRequester(Base):

    # 类线程锁
    API_KEY_LOCK = threading.Lock()

    def __init__(self, config: TranslatorConfig, plugin_manager: PluginManager) -> None:
        super().__init__()

        # 初始化
        self.config = config
        self.plugin_manager = plugin_manager

    # 发起请求
    def request(self, messages: list[dict], system_prompt: str, prompt_preset: int, model_degradation: bool) -> tuple[bool, str, int, int]:
        # 获取平台参数
        target_platform = self.config.target_platform
        api_format = self.config.platforms.get(target_platform).get("api_format")

        # 获取请求参数
        temperature, top_p, presence_penalty, frequency_penalty = self.get_platform_request_args()

        # 思考模型固定参数
        if prompt_preset == PromptBuilderEnum.THINK:
            temperature = 0.5
            top_p = 0.95

        # 如果上一次请求出现模型退化，更改参数
        frequency_penalty = 0.2 if model_degradation == True else frequency_penalty

        # 发起请求
        if target_platform == "sakura":
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_sakura(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        elif target_platform == "LocalLLM":
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_LocalLLM(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        elif target_platform == "cohere":
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_cohere(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        elif target_platform == "google":
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_google(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        elif target_platform == "anthropic" or (target_platform.startswith("custom_platform_") and api_format == "Anthropic"):
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_anthropic(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        else:
            skip, response_think, response_content, prompt_tokens, completion_tokens = self.request_openai(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )

        return skip, response_think, response_content, prompt_tokens, completion_tokens

    # 轮询获取key列表里的key
    def get_apikey(self) -> str:
        # 如果密钥列表长度为 0，则直接返回固定密钥
        # 如果密钥列表长度为 1，或者索引已达到最大长度，则重置索引
        # 否则切换到下一个密钥
        with TranslatorRequester.API_KEY_LOCK:
            if len(self.config.apikey_list) == 0:
                return "no_key_required"
            elif len(self.config.apikey_list) == 1 or self.config.apikey_index >= len(self.config.apikey_list) - 1:
                self.config.apikey_index = 0
                return self.config.apikey_list[self.config.apikey_index]
            else:
                self.config.apikey_index = self.config.apikey_index + 1
                return self.config.apikey_list[self.config.apikey_index]

    # 获取接口的请求参数
    def get_platform_request_args(self) -> tuple[float, float, float, float]:
        return (
            self.config.platforms.get(self.config.target_platform).get("temperature"),
            self.config.platforms.get(self.config.target_platform).get("top_p"),
            self.config.platforms.get(self.config.target_platform).get("presence_penalty"),
            self.config.platforms.get(self.config.target_platform).get("frequency_penalty"),
        )

    # 发起请求
    def request_sakura(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            client = OpenAI(
                base_url = self.config.base_url,
                api_key = self.get_apikey(),
            )

            response = client.chat.completions.create(
                model = self.config.model,
                messages = messages,
                top_p = top_p,
                temperature = temperature,
                frequency_penalty = frequency_penalty,
                timeout = self.config.request_timeout,
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

        # Sakura 返回的内容多行文本，将其转换为 JSON 字符串
        json_dict = {}
        for i, line in enumerate(response_content.strip().splitlines()):
            json_dict[str(i)] = line.strip()
        response_content = json.dumps(json_dict, ensure_ascii = False)

        return False, "", response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_LocalLLM(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            client = OpenAI(
                base_url = self.config.base_url,
                api_key = self.get_apikey(),
            )

            response = client.chat.completions.create(
                model = self.config.model,
                messages = messages,
                top_p = top_p,
                temperature = temperature,
                frequency_penalty = frequency_penalty,
                timeout = self.config.request_timeout,
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

        # 提取标签内翻译结果
        response_content = TranslatorRequester.extract_span_content_regex(self,response_content)

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


        # 返回的内容多行文本，将其转换为 JSON 字符串
        json_dict = {}
        for i, line in enumerate(response_content.strip().splitlines()):
            json_dict[str(i)] = line.strip()
        response_content = json.dumps(json_dict, ensure_ascii = False)


        # 还原换行符
        response_content = response_content.replace("@", "\n").replace("＠", "\n").replace("∞", "\r")


        return False, response_think, response_content, prompt_tokens, completion_tokens

    # 辅助函数，用于提取标签内文本
    def extract_span_content_regex(self,html_string):
        span_pattern = r'<span.*?>(.*?)</span>'  # 匹配 <text> 标签及其内容的正则表达式
        matches = re.findall(span_pattern, html_string, re.IGNORECASE | re.DOTALL) # 查找所有匹配项，忽略大小写和换行符

        if not matches:
            return html_string  # 如果没有匹配到 <text> 标签，返回原始字符串
        else:
            return "\n".join(matches) # 将匹配到的内容用空格连接成一个字符串并返回


    # 发起请求
    def request_cohere(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            # Cohere SDK 文档 - https://docs.cohere.com/reference/chat
            client = cohere.ClientV2(
                base_url = self.config.base_url,
                api_key = self.get_apikey(),
                timeout = self.config.request_timeout,
            )

            response = client.chat(
                model = self.config.model,
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
    def request_google(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            # Gemini SDK 文档 - https://ai.google.dev/api?hl=zh-cn&lang=python
            genai.configure(
                api_key = self.get_apikey(),
                transport = "rest",
            )

            model = genai.GenerativeModel(
                model_name = self.config.model,
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
                messages,
                generation_config = {
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_output_tokens": 4096,
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
    def request_anthropic(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            client = anthropic.Anthropic(
                base_url = self.config.base_url,
                api_key = self.get_apikey(),
            )

            response = client.messages.create(
                model = self.config.model,
                system = system_prompt,
                messages = messages,
                temperature = temperature,
                top_p = top_p,
                timeout = self.config.request_timeout,
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
    def request_openai(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            client = OpenAI(
                base_url = self.config.base_url,
                api_key = self.get_apikey(),
            )

            # 针对ds-r模型的特殊处理，因为该模型不支持模型预输入回复
            if self.config.model in {"deepseek-reasoner", "deepseek-r1", "DeepSeek-R1"}:
                # 检查一下最后的消息是否用户消息，以免误删。(用户使用了推理模型卻不切换为推理模型提示词的情况)
                if isinstance(messages[-1], dict) and messages[-1].get('role') != 'user':
                    messages = messages[:-1]  # 移除最后一个元素


            # 部分平台和模型不接受frequency_penalty参数
            if presence_penalty == 0 and frequency_penalty == 0:
                response = client.chat.completions.create(
                    model = self.config.model,
                    messages = messages,
                    temperature = temperature,
                    top_p = top_p,
                    timeout = self.config.request_timeout,
                )

            else:
                response = client.chat.completions.create(
                    model = self.config.model,
                    messages = messages,
                    temperature = temperature,
                    top_p = top_p,
                    presence_penalty = presence_penalty,
                    frequency_penalty = frequency_penalty,
                    timeout = self.config.request_timeout,
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