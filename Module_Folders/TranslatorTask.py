import time

import cohere                       # 需要安装库pip install cohere
import anthropic                    # 需要安装库pip install anthropic
import google.generativeai as genai # 需要安装库pip install -U google-generativeai
from openai import OpenAI           # 需要安装库pip install openai

from Base.AiNieeBase import AiNieeBase
from Module_Folders.Cache_Manager.Cache import Cache_Manager
from Module_Folders.Response_Parser.Response import Response_Parser

# 接口请求器
class TranslatorTask(AiNieeBase):

    def __init__(self, translator, configurator, plugin_manager, request_limiter):
        super().__init__()

        # 初始化
        self.translator = translator
        self.configurator = configurator
        self.plugin_manager = plugin_manager
        self.request_limiter = request_limiter

    # 并发接口请求分发
    def start(self):
        try:
            target_platform = self.configurator.target_platform
            api_format = self.configurator.platforms.get(target_platform).get("api_format")

            if target_platform == "sakura":
                return self.request_sakura()
            elif target_platform == "cohere":
                return self.request_cohere()
            elif target_platform == "google":
                return self.request_google()
            elif target_platform == "anthropic" or (target_platform.startswith("custom_platform_") and api_format == "Anthropic"):
                return self.request_anthropic()
            else:
                return self.request_openai()
        except Exception as e:
            self.error("网络请求错误 ...", e)

    # 发起请求
    def request_sakura(self):
        # 从缓存数据中获取文本并更新这些文本的状态
        with self.translator.cache_data_lock:
            if self.configurator.tokens_limit_switch == True and self.configurator.lines_limit_switch == False:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(
                    self,
                    self.configurator.tokens_limit,
                    self.configurator.cache_list,
                    self.configurator.pre_line_counts
                )

            if self.configurator.tokens_limit_switch == False and self.configurator.lines_limit_switch == True:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(
                    self,
                    self.configurator.lines_limit,
                    self.configurator.cache_list,
                    self.configurator.pre_line_counts
                )

        # 检查原文文本是否成功
        if len(source_text_list) == 0:
            self.warning("获取原文文本失败，即将取消该任务 ...")
            return {}

        # 将原文文本列表改变为请求格式
        source_text_dict, row_count = Cache_Manager.create_dictionary_from_list(self, source_text_list)

        # 如果原文是日语，清除文本首位中的代码文本，并记录清除信息
        if self.configurator.source_language == "日语" and self.configurator.text_clear_toggle:
            source_text_dict, process_info_list = Cache_Manager.process_dictionary(self, source_text_dict)
            row_count = len(source_text_dict)

        # 生成请求指令
        messages, source_text_str, previous_message, glossary_message = self.generate_prompt_sakura(
            source_text_dict,
            previous_list,
        )

        # 预估 Token 消费，并检查 RPM 和 TPM 限制
        request_tokens_consume = self.request_limiter.num_tokens_from_messages(messages)
        while True:
            # 检测是否需要停止任务
            if self.configurator.Running_status == self.STATUS.STOPING:
                return {}

            # 检查 RPM 和 TPM 限制，如果符合条件，则继续
            if self.request_limiter.RPM_and_TPM_limit(request_tokens_consume):
                break

            # 如果以上条件都不符合，则间隔 0.5 秒再次检查
            time.sleep(0.5)

        # 记录是否检测到模型退化
        model_degradation = False

        # 开始任务循环
        i = 0
        while i < self.configurator.retry_count_limit + 1:
            # 检测是否需要停止任务
            if self.configurator.Running_status == self.STATUS.STOPING:
                return {}

            # 记录任务循环次数
            i = i + 1

            # 记录开始请求时间
            start_request_time = time.time()

            # 获取接口的请求参数
            temperature, top_p, presence_penalty, frequency_penalty = self.configurator.get_platform_request_args()

            # 如果上一次请求出现模型退化，更改参数
            if model_degradation == True:
                frequency_penalty = 0.2

            extra_query = {
                "do_sample": True,
                "num_beams": 1,
                "repetition_penalty": 1.0
            }

            # 创建客户端
            client = OpenAI(
                base_url = self.configurator.base_url,
                api_key = self.configurator.get_apikey(),
            )

            # Token限制模式下，请求的最大tokens数应该与设置保持一致
            if self.configurator.tokens_limit_switch == True:
                max_tokens = self.configurator.tokens_limit
            else:
                max_tokens = 512

            # 发送对话请求
            try:
                response = client.chat.completions.create(
                    model = self.configurator.model,
                    messages = messages,
                    top_p = top_p,
                    temperature = temperature,
                    frequency_penalty = frequency_penalty,
                    stream = False,
                    timeout = 120,
                    max_tokens = max_tokens,
                    extra_query = extra_query,
                )

                # 提取回复的文本内容
                response_content = response.choices[0].message.content
            except Exception as e:
                self.error("翻译任务错误 ...", e)
                continue # 跳过后续步骤，直接重试

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

            # 见raw格式转换为josn格式字符串
            response_content_json = Response_Parser.convert_str_to_json_str(
                self,
                row_count,
                response_content
            )

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
                # 当检测到模型退化时，无论是否开启重试，均增加一次额外的重试次数，且仅增加一次
                if "高频" not in error_content or model_degradation == True:
                    self.warning(f"译文文本未通过检查，稍后将重试 - {error_content}")
                else:
                    i = i - 1
                    model_degradation = True
                    self.warning("译文文本中检查到模型退化现象，稍后将修改请求参数后重试...")
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

                self.print("")
                self.info(f"已完成翻译任务，耗时 {(time.time() - start_request_time):.2f} 秒 ...")
                self.info(f"文本行数 - {row_count}，指令 Tokens - {prompt_tokens}, 返回 Tokens - {completion_tokens}")
                if previous_message != "":
                    self.info(f"{previous_message.strip()}")
                if glossary_message != "":
                    self.info(f"{glossary_message.strip()}")
                self.info("※" * 80)
                self.print("")
                for source, translated in zip(source_text_str.splitlines(), response_content.splitlines()):
                    self.print(f"{source} [green]->[/] {translated}")
                self.print("")
                self.info("※" * 80)
                self.print("")

                # 翻译任务执行成功则不再重试
                break

        return {
            "check_result": check_result,
            "row_count": row_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }

    # 生成指令
    def generate_prompt_sakura(self, source_text_dict, previous_list):
        messages = []

        # 构建系统提示词
        system_prompt = {
            "role": "system",
            "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"
        }
        messages.append(system_prompt)

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
            previous_message = f"携带参考上文功能已开启，实际携带 {len(previous_list)} 行上文 ...\n{"\n".join(previous_list)}"

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
                glossary_message = f"指令词典功能已开启，本次请求中包含 {len(gpt_dict_text_list)} 个词典条目 ...\n{gpt_dict_raw_text}"

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

        return messages, source_text_str, previous_message, glossary_message

    # 将json文本改为纯文本
    def convert_dict_to_raw_str(self, source_text_dict):
        str_list = []

        for idx in range(len(source_text_dict.keys())):
            str_list.append(source_text_dict[f"{idx}"])

        return "\n".join(str_list)
