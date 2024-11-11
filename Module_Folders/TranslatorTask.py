import time
import itertools

import rapidjson as json
from rich import box
from rich.table import Table

import cohere                       # 需要安装库pip install cohere
import anthropic                    # 需要安装库pip install anthropic
import google.generativeai as genai # 需要安装库pip install -U google-generativeai
from openai import OpenAI           # 需要安装库pip install openai

from Base.Base import Base
from Module_Folders.Cache_Manager.Cache import Cache_Manager
from Module_Folders.Response_Parser.Response import Response_Parser

# 接口请求器
class TranslatorTask(Base):

    def __init__(self, translator, configurator, plugin_manager, request_limiter):
        super().__init__()

        # 初始化
        self.translator = translator
        self.configurator = configurator
        self.plugin_manager = plugin_manager
        self.request_limiter = request_limiter

    # 并发接口请求分发
    def start(self):
        return self.request(
            self.configurator.target_platform,
            self.configurator.platforms.get(self.configurator.target_platform).get("api_format"),
        )

    # 发起请求
    def request(self, target_platform, api_format):
        # 检测是否需要停止任务
        if self.configurator.status == Base.STATUS.STOPING:
            return {}

        # 从缓存数据中获取文本并更新这些文本的状态
        with self.translator.cache_data_lock:
            # 获取需要翻译的文本，Sakura 默认原文前文，其他模型有译文优先获取译文前文
            if self.configurator.tokens_limit_switch == True and target_platform == "sakura":
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(
                    self,
                    self.configurator.tokens_limit,
                    self.configurator.cache_list,
                    False,
                    self.configurator.pre_line_counts
                )
            elif self.configurator.tokens_limit_switch == True and target_platform != "sakura":
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(
                    self,
                    self.configurator.tokens_limit,
                    self.configurator.cache_list,
                    True,
                    self.configurator.pre_line_counts
                )
            elif self.configurator.tokens_limit_switch == False and target_platform == "sakura":
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(
                    self,
                    self.configurator.lines_limit,
                    self.configurator.cache_list,
                    False,
                    self.configurator.pre_line_counts
                )
            elif self.configurator.tokens_limit_switch == False and target_platform != "sakura":
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(
                    self,
                    self.configurator.lines_limit,
                    self.configurator.cache_list,
                    True,
                    self.configurator.pre_line_counts
                )

        # 检查原文文本是否成功
        if len(source_text_list) == 0:
            return {}

        # 将原文文本列表改变为请求格式
        source_text_dict, row_count = Cache_Manager.create_dictionary_from_list(self, source_text_list)

        # 如果原文是日语，清除文本首位中的代码文本，并记录清除信息
        if self.configurator.source_language == "日语" and self.configurator.text_clear_toggle:
            source_text_dict, process_info_list = Cache_Manager.process_dictionary(self, source_text_dict)
            row_count = len(source_text_dict)

        # 生成请求指令
        if target_platform == "sakura":
            messages, system_prompt, extra_log = self.generate_prompt_sakura(
                source_text_dict,
                previous_list,
            )
        else:
            messages, system_prompt, extra_log = self.generate_prompt(
                target_platform,
                api_format,
                source_text_dict,
                previous_list
            )

        # 预估 Token 消费，并检查 RPM 和 TPM 限制
        request_tokens_consume = self.request_limiter.num_tokens_from_messages(messages)

        # 记录是否检测到模型退化
        model_degradation = False

        # 开始任务循环
        i = 0
        while i < self.configurator.retry_count_limit + 1:
            # 记录任务开始的的时间
            task_start_time = time.time()

            while True:
                # 检查是否超时，超时则直接跳过当前任务，以避免死循环
                if time.time() - task_start_time >= self.configurator.request_timeout:
                    return {}

                # 检测是否需要停止任务
                if self.configurator.status == Base.STATUS.STOPING:
                    return {}

                # 检查 RPM 和 TPM 限制，如果符合条件，则继续
                if self.request_limiter.RPM_and_TPM_limit(request_tokens_consume):
                    break

                # 如果以上条件都不符合，则间隔 0.5 秒再次检查
                time.sleep(0.5)

            # 记录任务循环次数
            i = i + 1

            # 获取接口的请求参数
            temperature, top_p, presence_penalty, frequency_penalty = self.configurator.get_platform_request_args()

            # 如果上一次请求出现模型退化，更改参数
            if model_degradation == True:
                frequency_penalty = 0.2

            # 发起请求
            if target_platform == "sakura":
                skip, response_content_json, prompt_tokens, completion_tokens = self.request_sakura(
                    messages,
                    system_prompt,
                    temperature,
                    top_p,
                    presence_penalty,
                    frequency_penalty
                )
            elif target_platform == "cohere":
                skip, response_content_json, prompt_tokens, completion_tokens = self.request_cohere(
                    messages,
                    system_prompt,
                    temperature,
                    top_p,
                    presence_penalty,
                    frequency_penalty
                )
            elif target_platform == "google":
                skip, response_content_json, prompt_tokens, completion_tokens = self.request_google(
                    messages,
                    system_prompt,
                    temperature,
                    top_p,
                    presence_penalty,
                    frequency_penalty
                )
            elif target_platform == "anthropic" or (target_platform.startswith("custom_platform_") and api_format == "Anthropic"):
                skip, response_content_json, prompt_tokens, completion_tokens = self.request_anthropic(
                    messages,
                    system_prompt,
                    temperature,
                    top_p,
                    presence_penalty,
                    frequency_penalty
                )
            else:
                skip, response_content_json, prompt_tokens, completion_tokens = self.request_openai(
                    messages,
                    system_prompt,
                    temperature,
                    top_p,
                    presence_penalty,
                    frequency_penalty
                )

            # 如果请求结果标记为 skip，即有错误发生，则跳过本次循环
            if skip == True:
                continue

            # 提取回复内容
            response_dict = Response_Parser.text_extraction(
                self,
                response_content_json
            )

            # 检查回复内容
            check_result, error_content = Response_Parser.check_response_content(
                self,
                self.configurator.reply_check_switch,
                response_content_json,
                response_dict,
                source_text_dict,
                self.configurator.source_language
            )

            # 判断结果是否通过检查
            if check_result == False:
                error = ""
                if "退化" not in error_content or model_degradation == True:
                    error = f"译文文本未通过检查，稍后将重试 - {error_content}"
                else:
                    i = i - 1 # 当检测到模型退化时，无论是否开启重试，均增加一次额外的重试次数，且仅增加一次
                    model_degradation = True
                    error = "译文文本中检查到模型退化现象，稍后将修改请求参数后重试"

                # 打印任务结果
                self.print("")
                self.print(
                    self.generate_log_table(
                        *self.generate_log_rows(
                            error,
                            task_start_time,
                            row_count,
                            prompt_tokens,
                            completion_tokens,
                            [v.get("source_text") for v in source_text_list],
                            [v for _, v in response_dict.items()],
                            extra_log
                        )
                    )
                )
                self.print("")
            else:
                # 强制开启换行符还原功能
                response_dict = Cache_Manager.replace_special_characters(
                    self,
                    response_dict,
                    "还原"
                )

                # 如果开启译后文本替换功能，则根据用户字典进行替换
                if self.configurator.post_translation_switch:
                    response_dict = self.configurator.replace_after_translation(response_dict)

                # 如果原文是日语，则还原文本的首尾代码字符
                if self.configurator.source_language == "日语" and self.configurator.text_clear_toggle:
                    response_dict = Cache_Manager.update_dictionary(self, response_dict, process_info_list)

                # 更新缓存数据
                with self.translator.cache_data_lock:
                    Cache_Manager.update_cache_data(
                        self,
                        self.configurator.cache_list,
                        source_text_list,
                        response_dict,
                        self.configurator.model
                    )

                # 打印任务结果
                self.print("")
                self.print(
                    self.generate_log_table(
                        *self.generate_log_rows(
                            "",
                            task_start_time,
                            row_count,
                            prompt_tokens,
                            completion_tokens,
                            [v.get("source_text") for v in source_text_list],
                            [v for _, v in response_dict.items()],
                            extra_log
                        )
                    )
                )
                self.print("")

                # 翻译任务执行成功则不再重试
                break

        # 返回任务结果，如果 check_result 不存在，即请求发生错误，则按照失败处理
        try:
            check_result == True
            return {
                "check_result": check_result,
                "row_count": row_count,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        except Exception:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": request_tokens_consume,
                "completion_tokens": 0,
            }

    # 发起请求
    def request_sakura(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty):
        try:
            client = OpenAI(
                base_url = self.configurator.base_url,
                api_key = self.configurator.get_apikey(),
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

        return False, self.convert_str_to_json_str(response_content), prompt_tokens, completion_tokens

    # 发起请求
    def request_cohere(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty):
        try:
            # Cohere SDK 文档 - https://docs.cohere.com/reference/chat
            client = cohere.ClientV2(
                base_url = self.configurator.base_url,
                api_key = self.configurator.get_apikey(),
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
            response_content_json = response.message.content[0].text
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
            response_content_json
        )

        return False, response_content_json, prompt_tokens, completion_tokens

    # 发起请求
    def request_google(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty):
        try:
            # Gemini SDK 文档 - https://ai.google.dev/api?hl=zh-cn&lang=python
            genai.configure(
                api_key = self.configurator.get_apikey(),
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
            response_content_json = response.text
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
            response_content_json
        )

        return False, response_content_json, prompt_tokens, completion_tokens

    # 发起请求
    def request_anthropic(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty):
        try:
            client = anthropic.Anthropic(
                base_url = self.configurator.base_url,
                api_key = self.configurator.get_apikey(),
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
            response_content_json = response.content[0].text
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
            response_content_json
        )

        return False, response_content_json, prompt_tokens, completion_tokens

    # 发起请求
    def request_openai(self, messages, system_prompt, temperature, top_p, presence_penalty, frequency_penalty):
        try:
            client = OpenAI(
                base_url = self.configurator.base_url,
                api_key = self.configurator.get_apikey(),
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
            response_content_json = response.choices[0].message.content
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
            response_content_json
        )

        return False, response_content_json, prompt_tokens, completion_tokens

    # 生成指令
    def generate_prompt(self, target_platform, api_format, source_text_dict, previous_list):
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 获取基础系统提示词
        system_prompt = self.configurator.get_system_prompt()

        # 如果开启指令词典
        glossary = ""
        glossary_cot = ""
        if self.configurator.prompt_dictionary_switch:
            glossary, glossary_cot = self.configurator.build_glossary_prompt(source_text_dict, self.configurator.cn_prompt_toggle)
            if glossary:
                system_prompt += glossary
                extra_log.append(f"指令词典已添加：\n{glossary}")

        # 如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if self.configurator.characterization_switch:
            characterization, characterization_cot = self.configurator.build_characterization(source_text_dict, self.configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization
                extra_log.append(f"角色介绍已添加：\n{characterization}")

        # 如果启用自定义世界观设定功能
        world_building = ""
        world_building_cot = ""
        if self.configurator.world_building_switch:
            world_building, world_building_cot = self.configurator.build_world(self.configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building
                extra_log.append(f"世界观设定已添加：\n{world_building}")

        # 如果启用自定义行文措辞要求功能
        writing_style = ""
        writing_style_cot = ""
        if self.configurator.writing_style_switch:
            writing_style, writing_style_cot = self.configurator.build_writing_style(self.configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style
                extra_log.append(f"行文措辞要求已添加：\n{writing_style}")

        # 获取默认示例前置文本
        pre_prompt = self.configurator.build_userExamplePrefix(
            self.configurator.cn_prompt_toggle,
            self.configurator.cot_toggle
        )
        fol_prompt = self.configurator.build_modelExamplePrefix(
            self.configurator.cn_prompt_toggle,
            self.configurator.cot_toggle,
            self.configurator.source_language,
            self.configurator.target_language,
            glossary_cot,
            characterization_cot,
            world_building_cot,
            writing_style_cot
        )

        # 获取默认示例
        original_exmaple, translation_example_content = self.configurator.build_translation_sample(
            source_text_dict,
            self.configurator.source_language,
            self.configurator.target_language
        )
        if original_exmaple and translation_example_content:
            messages.append({
                "role": "user",
                "content": f"{pre_prompt}```json\n{original_exmaple}\n```"
            })
            messages.append({
                "role": "assistant",
                "content": f"{fol_prompt}```json\n{translation_example_content}\n```"
            })
            extra_log.append(f"格式原文示例已添加：\n{original_exmaple}")
            extra_log.append(f"格式译文示例已添加：\n{translation_example_content}")

        # 如果启用翻译风格示例功能
        if self.configurator.translation_example_switch:
            original_exmaple_3, translation_example_3 = self.configurator.build_translation_example()
            if original_exmaple_3 and translation_example_3:
                messages.append({
                    "role": "user",
                    "content": original_exmaple_3
                })
                messages.append({
                    "role": "assistant",
                    "content": translation_example_3
                })
                extra_log.append(f"用户原文示例已添加：\n{original_exmaple_3}")
                extra_log.append(f"用户译文示例已添加：\n{translation_example_3}")

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "normalize_text",
            self.configurator,
            source_text_dict
        )

        # 如果开启了保留换行符功能
        if self.configurator.preserve_line_breaks_toggle:
            source_text_dict = Cache_Manager.replace_special_characters(
                self,
                source_text_dict,
                "替换"
            )

        # 如果开启译前文本替换功能，则根据用户字典进行替换
        if self.configurator.pre_translation_switch:
            source_text_dict = self.configurator.replace_before_translation(source_text_dict)

        # 如果加上文
        previous = ""
        if self.configurator.pre_line_counts and previous_list:
            previous = self.configurator.build_pre_text(
                previous_list,
                self.configurator.cn_prompt_toggle
            )
            if previous:
                extra_log.append(f"参考上文已添加：\n{"\n".join(previous_list)}")

        # 获取提问时的前置文本
        pre_prompt = self.configurator.build_userQueryPrefix(
            self.configurator.cn_prompt_toggle,
            self.configurator.cot_toggle
        )
        fol_prompt = self.configurator.build_modelResponsePrefix(
            self.configurator.cn_prompt_toggle,
            self.configurator.cot_toggle
        )

        # 构建用户信息
        source_text_str = json.dumps(
            source_text_dict,
            ensure_ascii = False
        )
        source_text_str = f"{previous}\n{pre_prompt}```json\n{source_text_str}\n```"

        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": fol_prompt
            }
        )

        # 当目标为 google 系列接口时，转换 messages 的格式
        # 当目标为 anthropic 兼容接口时，保持原样
        # 当目标为其他接口时，添加系统指令
        if target_platform == "google":
            new = []
            for m in messages:
                new.append({
                    "role": "model" if m.get("role", "") == "assistant" else m.get("role", ""),
                    "parts": m.get("content", ""),
                })
            messages = new
        elif target_platform == "anthropic" or (target_platform.startswith("custom_platform_") and api_format == "Anthropic"):
            pass
        else:
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": system_prompt
                }
            )

        return messages, system_prompt, extra_log

    # 生成指令 Sakura
    def generate_prompt_sakura(self, source_text_dict, previous_list):
        # 储存额外日志
        extra_log = []
        # 储存主体指令
        messages = []

        # 构建系统提示词
        messages.append({
            "role": "system",
            "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"
        })

        # 调用插件，进行处理
        self.plugin_manager.broadcast_event(
            "normalize_text",
            self.configurator,
            source_text_dict
        )

        # 如果开启译前替换功能
        if self.configurator.pre_translation_switch:
            source_text_dict = self.configurator.replace_before_translation(source_text_dict)

        # 如果开启了保留句内换行符功能
        if self.configurator.preserve_line_breaks_toggle:
            source_text_dict = Cache_Manager.replace_special_characters(
                self,
                source_text_dict,
                "替换"
            )

        # 如果开启了携带上文功能，v0.9 版本跳过
        previous_message = ""
        if self.configurator.model != "Sakura-v0.9" and self.configurator.pre_line_counts and previous_list:
            messages.append({
                "role": "user",
                "content": "将下面的日文文本翻译成中文：" + "\n".join(previous_list),
            })
            extra_log.append(f"参考上文已添加：\n{"\n".join(previous_list)}")

        # 如果开启了指令词典功能
        glossary_message = ""
        gpt_dict_raw_text = ""  # 空变量
        if self.configurator.model != "Sakura-v0.9" and self.configurator.prompt_dictionary_switch:  # v0.9 版本或功能未启用时跳过
            glossary_prompt = self.configurator.build_glossary_prompt_sakura(source_text_dict)
            if glossary_prompt:
                gpt_dict_text_list = []
                for gpt in glossary_prompt:
                    src = gpt["src"]
                    dst = gpt["dst"]
                    info = gpt["info"] if "info" in gpt.keys() else None
                    if info:
                        single = f"{src}->{dst} #{info}"
                    else:
                        single = f"{src}->{dst}"
                    gpt_dict_text_list.append(single)

                gpt_dict_raw_text = "\n".join(gpt_dict_text_list)
                extra_log.append(f"指令词典已添加：\n{gpt_dict_raw_text}")

        # 将原文本字典转换成raw格式的字符串
        source_text_str = self.convert_dict_to_raw_str(source_text_dict)

        # 构建主要提示词
        if gpt_dict_raw_text == "":
            user_prompt = "将下面的日文文本翻译成中文：\n" + source_text_str
        else:
            user_prompt = "根据以下术语表（可以为空）：\n" + gpt_dict_raw_text + "\n" + "将下面的日文文本根据对应关系和备注翻译成中文：\n" + source_text_str

        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        return messages, "", extra_log

    # 生成日志行
    def generate_log_rows(self, error, start_time, row_count, prompt_tokens, completion_tokens, source, translated, extra_log):
        rows = []

        if error != "":
            rows.append(error)
        else:
            rows.append(
                f"任务耗时 {(time.time() - start_time):.2f} 秒，"
                + f"文本行数 {row_count} 行，指令消耗 {prompt_tokens} Tokens，补全消耗 {completion_tokens} Tokens"
            )

        # 添加额外日志
        for v in extra_log:
            rows.append(v.strip())

        # 原文译文对比
        pair = ""
        for source, translated in itertools.zip_longest(source, translated, fillvalue = ""):
            pair = pair + "\n" + f"{source} [bright_blue]-->[/] {translated}"
        rows.append(pair.strip())

        return rows, error == ""

    # 生成日志表格
    def generate_log_table(self, rows: list, success: bool):
        table = Table(
            box = box.ASCII2,
            expand = True,
            highlight = True,
            show_lines = True,
            show_header = False,
            border_style = "green" if success else "red",
        )
        table.add_column("", style = "white", ratio = 1, overflow = "fold")

        for row in rows:
            if isinstance(row, str):
                table.add_row(row)
            else:
                table.add_row(*row)

        return table

    # 将json文本改为纯文本
    def convert_dict_to_raw_str(self, source_text_dict):
        str_list = []

        for idx in range(len(source_text_dict.keys())):
            str_list.append(source_text_dict[f"{idx}"])

        return "\n".join(str_list)

    # 将Raw文本恢复根据行数转换成json文本
    def convert_str_to_json_str(self, input_str):
        data = {}
        for idx, line in enumerate(input_str.strip().splitlines()):
            data[f"{idx}"] = f"{line}"

        return json.dumps(data, ensure_ascii = False)