import threading

import cohere                           # pip install cohere
import anthropic                        # pip install anthropic
import google.generativeai as genai     # pip install google-generativeai
from openai import OpenAI               # pip install openai

import rapidjson as json

from Base.Base import Base
from Base.PluginManager import PluginManager
from Module_Folders.Configurator.Config import Configurator

# 接口请求器
class TranslatorRequester(Base):

    # 类线程锁
    API_KEY_LOCK = threading.Lock()

    def __init__(self, configurator: Configurator, plugin_manager: PluginManager) -> None:
        super().__init__()

        # 初始化
        self.configurator = configurator
        self.plugin_manager = plugin_manager

    # 发起请求
    def request(self, messages: list[dict], system_prompt: str, model_degradation: bool) -> tuple[bool, str, int, int]:
        # 获取平台参数
        target_platform = self.configurator.target_platform
        api_format = self.configurator.platforms.get(target_platform).get("api_format")

        # 获取请求参数
        temperature, top_p, presence_penalty, frequency_penalty = self.get_platform_request_args()

        # 如果上一次请求出现模型退化，更改参数
        frequency_penalty = 0.2 if model_degradation == True else frequency_penalty

        if target_platform == "sakura":
            skip, response_content, prompt_tokens, completion_tokens = self.request_sakura(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        elif target_platform == "cohere":
            skip, response_content, prompt_tokens, completion_tokens = self.request_cohere(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        elif target_platform == "google":
            skip, response_content, prompt_tokens, completion_tokens = self.request_google(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        elif target_platform == "anthropic" or (target_platform.startswith("custom_platform_") and api_format == "Anthropic"):
            skip, response_content, prompt_tokens, completion_tokens = self.request_anthropic(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )
        else:
            skip, response_content, prompt_tokens, completion_tokens = self.request_openai(
                messages,
                system_prompt,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            )

        return skip, response_content, prompt_tokens, completion_tokens

    # 轮询获取key列表里的key
    def get_apikey(self) -> str:
        # 如果密钥列表长度为 0，则直接返回固定密钥
        # 如果密钥列表长度为 1，或者索引已达到最大长度，则重置索引
        # 否则切换到下一个密钥
        with TranslatorRequester.API_KEY_LOCK:
            if len(self.configurator.apikey_list) == 0:
                return "no_key_required"
            elif len(self.configurator.apikey_list) == 1 or self.configurator.apikey_index >= len(self.configurator.apikey_list) - 1:
                self.configurator.apikey_index = 0
                return self.configurator.apikey_list[self.configurator.apikey_index]
            else:
                self.configurator.apikey_index = self.configurator.apikey_index + 1
                return self.configurator.apikey_list[self.configurator.apikey_index]

    # 获取接口的请求参数
    def get_platform_request_args(self) -> tuple[float, float, float, float]:
        return (
            self.configurator.platforms.get(self.configurator.target_platform).get("temperature"),
            self.configurator.platforms.get(self.configurator.target_platform).get("top_p"),
            self.configurator.platforms.get(self.configurator.target_platform).get("presence_penalty"),
            self.configurator.platforms.get(self.configurator.target_platform).get("frequency_penalty"),
        )

    # 发起请求
    def request_sakura(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            client = OpenAI(
                base_url = self.configurator.base_url,
                api_key = self.get_apikey(),
            )

            response = client.chat.completions.create(
                model = self.configurator.model,
                messages = messages,
                top_p = top_p,
                temperature = temperature,
                frequency_penalty = frequency_penalty,
                timeout = self.configurator.request_timeout,
                max_tokens = max(512, self.configurator.tokens_limit) if self.configurator.tokens_limit_switch == True else 512,
                extra_query = {
                    "do_sample": True,
                    "num_beams": 1,
                    "repetition_penalty": 1.0
                },
            )

            # 提取回复的文本内容
            response_content = response.choices[0].message.content
        except Exception as e:
            if self.is_debug():
                self.error("翻译任务错误 ...", e)
            else:
                self.error(f"翻译任务错误 ... {e}", None)
            return True, None, None, None

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

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "sakura_complete_text_process",
            self.configurator,
            response_content
        )

        # Sakura 返回的内容多行文本，将其转换为 JSON 字符串
        json_dict = {}
        for i, line in enumerate(response_content.strip().splitlines()):
            json_dict[str(i)] = line.strip()
        response_content = json.dumps(json_dict, ensure_ascii = False)

        return False, response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_cohere(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            # Cohere SDK 文档 - https://docs.cohere.com/reference/chat
            client = cohere.ClientV2(
                base_url = self.configurator.base_url,
                api_key = self.get_apikey(),
                timeout = self.configurator.request_timeout,
            )

            response = client.chat(
                model = self.configurator.model,
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
            if self.is_debug():
                self.error("翻译任务错误 ...", e)
            else:
                self.error(f"翻译任务错误 ... {e}", None)
            return True, None, None, None

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

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "complete_text_process",
            self.configurator,
            response_content
        )

        return False, response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_google(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            # Gemini SDK 文档 - https://ai.google.dev/api?hl=zh-cn&lang=python
            genai.configure(
                api_key = self.get_apikey(),
                transport = "rest",
            )

            model = genai.GenerativeModel(
                model_name = self.configurator.model,
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
            if self.is_debug():
                self.error("翻译任务错误 ...", e)
            else:
                self.error(f"翻译任务错误 ... {e}", None)
            return True, None, None, None

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

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "complete_text_process",
            self.configurator,
            response_content
        )

        return False, response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_anthropic(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            client = anthropic.Anthropic(
                base_url = self.configurator.base_url,
                api_key = self.get_apikey(),
            )

            response = client.messages.create(
                model = self.configurator.model,
                system = system_prompt,
                messages = messages,
                temperature = temperature,
                top_p = top_p,
                timeout = self.configurator.request_timeout,
                max_tokens = 4096,
            )

            # 提取回复的文本内容
            response_content = response.content[0].text
        except Exception as e:
            if self.is_debug():
                self.error("翻译任务错误 ...", e)
            else:
                self.error(f"翻译任务错误 ... {e}", None)
            return True, None, None, None

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

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "complete_text_process",
            self.configurator,
            response_content
        )

        return False, response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_openai(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty) -> tuple[bool, str, int, int]:
        try:
            client = OpenAI(
                base_url = self.configurator.base_url,
                api_key = self.get_apikey(),
            )

            response = client.chat.completions.create(
                model = self.configurator.model,
                messages = messages,
                temperature = temperature,
                top_p = top_p,
                presence_penalty = presence_penalty,
                frequency_penalty = frequency_penalty,
                timeout = self.configurator.request_timeout,
                max_tokens = 4096,
            )

            # 提取回复的文本内容
            response_content = response.choices[0].message.content
        except Exception as e:
            if self.is_debug():
                self.error("翻译任务错误 ...", e)
            else:
                self.error(f"翻译任务错误 ... {e}", None)
            return True, None, None, None

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

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "complete_text_process",
            self.configurator,
            response_content
        )

        return False, response_content, prompt_tokens, completion_tokens