import copy
import re
import time
import itertools

import rapidjson as json
from rich import box
from rich.table import Table

from Base.Base import Base
from Base.PluginManager import PluginManager
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig
from ModuleFolders.Translator.TranslatorRequester import TranslatorRequester
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilderThink import PromptBuilderThink
from ModuleFolders.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal
from ModuleFolders.PromptBuilder.PromptBuilderSakura import PromptBuilderSakura
from ModuleFolders.PromptBuilder.PromptBuilderDouble import PromptBuilderDouble
from ModuleFolders.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.RequestLimiter.RequestLimiter import RequestLimiter
from ModuleFolders.Cache.CacheManager import CacheManager



# 接口请求器
class TranslatorTask(Base):

    # 可能存在的空字符
    SPACE_PATTERN = r"\s*"

    # 用于英文的代码段规则
    CODE_PATTERN_EN = (
        SPACE_PATTERN + r"if\(.{0,5}[vs]\[\d+\].{0,10}\)" + SPACE_PATTERN,            # if(!s[982]) if(s[1623]) if(v[982] >= 1)
        SPACE_PATTERN + r"en\(.{0,5}[vs]\[\d+\].{0,10}\)" + SPACE_PATTERN,            # en(!s[982]) en(v[982] >= 1)
        SPACE_PATTERN + r"[/\\][a-z]{1,5}<[\d]{0,10}>" + SPACE_PATTERN,               # /C<1> \FS<12>
        SPACE_PATTERN + r"[/\\][a-z]{1,5}\[[\d]{0,10}\]" + SPACE_PATTERN,             # /C[1] \FS[12]
        SPACE_PATTERN + r"[/\\][a-z]{1,5}(?=<[^\d]{0,10}>)" + SPACE_PATTERN,          # /C<非数字> \FS<非数字> 中的前半部分
        SPACE_PATTERN + r"[/\\][a-z]{1,5}(?=\[[^\d]{0,10}\])" + SPACE_PATTERN,        # /C[非数字] \FS[非数字] 中的前半部分
    )

    # 用于非英文的代码段规则
    CODE_PATTERN_NON_EN = (
        SPACE_PATTERN + r"if\(.{0,5}[vs]\[\d+\].{0,10}\)" + SPACE_PATTERN,            # if(!s[982]) if(v[982] >= 1) if(v[982] >= 1)
        SPACE_PATTERN + r"en\(.{0,5}[vs]\[\d+\].{0,10}\)" + SPACE_PATTERN,            # en(!s[982]) en(v[982] >= 1)
        SPACE_PATTERN + r"[/\\][a-z]{1,5}<[a-z\d]{0,10}>" + SPACE_PATTERN,            # /C<y> /C<1> \FS<xy> \FS<12>
        SPACE_PATTERN + r"[/\\][a-z]{1,5}\[[a-z\d]{0,10}\]" + SPACE_PATTERN,          # /C[x] /C[1] \FS[xy] \FS[12]
        SPACE_PATTERN + r"[/\\][a-z]{1,5}(?=<[^a-z\d]{0,10}>)" + SPACE_PATTERN,       # /C<非数字非字母> \FS<非数字非字母> 中的前半部分
        SPACE_PATTERN + r"[/\\][a-z]{1,5}(?=\[[^a-z\d]{0,10}\])" + SPACE_PATTERN,     # /C[非数字非字母] \FS[非数字非字母] 中的前半部分
    )

    # 同时作用于英文于非英文的代码段规则
    CODE_PATTERN_COMMON = (
        SPACE_PATTERN + r"\\fr" + SPACE_PATTERN,                                      # 重置文本的改变
        SPACE_PATTERN + r"\\fb" + SPACE_PATTERN,                                      # 加粗
        SPACE_PATTERN + r"\\fi" + SPACE_PATTERN,                                      # 倾斜
        SPACE_PATTERN + r"\\\{" + SPACE_PATTERN,                                      # 放大字体 \{
        SPACE_PATTERN + r"\\\}" + SPACE_PATTERN,                                      # 缩小字体 \}
        SPACE_PATTERN + r"\\g" + SPACE_PATTERN,                                       # 显示货币 \G
        SPACE_PATTERN + r"\\\$" + SPACE_PATTERN,                                      # 打开金币框 \$
        SPACE_PATTERN + r"\\\." + SPACE_PATTERN,                                      # 等待0.25秒 \.
        SPACE_PATTERN + r"\\\|" + SPACE_PATTERN,                                      # 等待1秒 \|
        SPACE_PATTERN + r"\\!" + SPACE_PATTERN,                                       # 等待按钮按下 \!
        SPACE_PATTERN + r"\\>" + SPACE_PATTERN,                                       # 在同一行显示文字 \>
        # SPACE_PATTERN + r"\\<" + SPACE_PATTERN,                                     # 取消显示所有文字 \<
        SPACE_PATTERN + r"\\\^" + SPACE_PATTERN,                                      # 显示文本后不需要等待 \^
        # SPACE_PATTERN + r"\\n" + SPACE_PATTERN,                                     # 换行符 \\n
        SPACE_PATTERN + r"\\\\<br>" + SPACE_PATTERN,                                  # 换行符 \\<br>
        SPACE_PATTERN + r"<br>" + SPACE_PATTERN,                                      # 换行符 <br>
        "" + r"\r" + "",                                                              # 换行符 \r，该字符本来就是 SPACE_PATTERN 的一部分，不再添加前后缀，避免死循环
        "" + r"\n" + "",                                                              # 换行符 \n，该字符本来就是 SPACE_PATTERN 的一部分，不再添加前后缀，避免死循环

        SPACE_PATTERN + r'class=".*?">(?!<)' + SPACE_PATTERN,                         # class="toc1"><a href="18_Chapter08.html">正文</a>或者class="toc1">>正文， epub小说的跳转目录
        SPACE_PATTERN + r"</a>" + SPACE_PATTERN,                                      # 是以“class=”开头，中间任意内容，然后以“">”结束，“">”尽可能后面，且不是跟着<。

        SPACE_PATTERN + r"\\SE\[.{0,15}?\]" + SPACE_PATTERN,                          # se控制代码

        SPACE_PATTERN + r'【\\[A-Za-z]+\[[^]]*】\\SE\[[^]]*\]'+ SPACE_PATTERN,        #【\N[1]】\SE[xxx]
    )

    def __init__(self, config: TranslatorConfig, plugin_manager: PluginManager, request_limiter: RequestLimiter, cache_manager: CacheManager) -> None:
        super().__init__()

        # 初始化
        self.config = config
        self.plugin_manager = plugin_manager
        self.request_limiter = request_limiter
        self.cache_manager = cache_manager

        # 初始化参数
        self.messages = []
        self.messages_a = []  
        self.messages_b = []    
        self.system_prompt = ""  
        self.system_prompt_a = ""  
        self.system_prompt_b = ""  

        self.extra_log = []


        # 占位符替换字典
        self.replace_dict = {}


        # 根据原文语言生成正则表达式
        if "英语" in config.source_language:
            code_pattern = TranslatorTask.CODE_PATTERN_EN + TranslatorTask.CODE_PATTERN_COMMON
            self.prefix_pattern = re.compile(f"^(?:{"|".join(code_pattern)})+", flags = re.IGNORECASE)
            self.suffix_pattern = re.compile(f"(?:{"|".join(code_pattern)})+$", flags = re.IGNORECASE)
        else:
            code_pattern = TranslatorTask.CODE_PATTERN_NON_EN + TranslatorTask.CODE_PATTERN_COMMON
            self.prefix_pattern = re.compile(f"^(?:{"|".join(code_pattern)})+", flags = re.IGNORECASE)
            self.suffix_pattern = re.compile(f"(?:{"|".join(code_pattern)})+$", flags = re.IGNORECASE)

    # 启动任务
    def start(self) -> dict:
        if self.config.double_request_switch_settings == True:
            return self.unit_DRtranslation_task()
        else:
            return self.unit_translation_task()

    # 单请求翻译任务
    def unit_translation_task(self) -> dict:
        # 任务开始的时间
        task_start_time = time.time()

        while True:
            # 检测是否收到停止翻译事件
            if Base.work_status == Base.STATUS.STOPING:
                return {}

            # 检查是否超时，超时则直接跳过当前任务，以避免死循环
            if time.time() - task_start_time >= self.config.request_timeout:
                return {}

            # 检查 RPM 和 TPM 限制，如果符合条件，则继续
            if self.request_limiter.check_limiter(self.request_tokens_consume):
                break

            # 如果以上条件都不符合，则间隔 1 秒再次检查
            time.sleep(1)

        # 获取接口配置信息包
        platform_config = self.config.get_platform_configuration("singleReq")

        # 读取术语表更新系统提示词,因为核心流程限制，而加上的挫版补丁.....
        self.system_prompt = self.update_sysprompt_glossary(self.config,self.system_prompt, self.config.prompt_dictionary_data, self.source_text_dict)

        # 发起请求
        requester = TranslatorRequester(self.config, self.plugin_manager)
        skip, response_think, response_content, prompt_tokens, completion_tokens = requester.sent_request(
            self.messages,
            self.system_prompt,
            platform_config
        )

        # 如果请求结果标记为 skip，即有运行错误发生，则直接返回错误信息，停止后续任务
        if skip == True:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

        # 提取回复内容
        response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content)

        # 检查回复内容
        check_result, error_content = ResponseChecker.check_response_content(
            self,
            self.config.response_check_switch,
            response_content,
            response_dict,
            self.source_text_dict,
            self.config.source_language
        )

        # 模型回复日志
        if response_think != "":
            self.extra_log.append("模型思考内容：\n" + response_think)
        if self.is_debug():
            self.extra_log.append("模型回复内容：\n" + response_content)

        # 检查译文
        if check_result == False:
            error = f"译文文本未通过检查，将在下一轮次的翻译中重新翻译 - {error_content}"

            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        error,
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        self.source_text_dict.values(),
                        response_dict.values(),
                        self.extra_log,
                    )
                )
            )
        else:
            # 各种还原步骤
            # 先复制一份，以免影响原有数据，response_dict 为字符串字典，所以浅拷贝即可
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.restore_all(restore_response_dict, self.prefix_codes, self.suffix_codes)

            # 更新译文结果到缓存数据中
            for item, response in zip(self.items, restore_response_dict.values()):
                item.set_model(self.config.model)
                item.set_translated_text(response)
                item.set_translation_status(CacheItem.STATUS.TRANSLATED)

            # 更新术语表与禁翻表到配置文件中
            self.config.update_glossary_ntl_config(glossary_result, NTL_result)


            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        "",
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        self.source_text_dict.values(),
                        response_dict.values(),
                        self.extra_log,
                    )
                )
            )


        # 否则返回译文检查的结果
        if check_result == False:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }
        else:
            return {
                "check_result": check_result,
                "row_count": self.row_count,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }


    # 双请求翻译任务
    def unit_DRtranslation_task(self) -> dict:
        # 任务开始的时间
        task_start_time = time.time()

        while True:
            # 检测是否收到停止翻译事件
            if Base.work_status == Base.STATUS.STOPING:
                return {}

            # 检查是否超时，超时则直接跳过当前任务，以避免死循环
            if time.time() - task_start_time >= self.config.request_timeout:
                return {}

            # 检查 RPM 和 TPM 限制，如果符合条件，则继续
            if self.request_limiter.check_limiter(self.request_tokens_consume):
                break


            # 如果以上条件都不符合，则间隔 1 秒再次检查
            time.sleep(1)


        # 构造初始替换字典
        previous_text = PromptBuilderDouble.get_previous_text(self, self.previous_text_list) # 上文
        source_text_str = PromptBuilderDouble.get_source_text(self, self.source_text_dict) # 原文
        glossary = PromptBuilderDouble.get_glossary(self, self.config, self.source_text_dict) # 术语表
        code = PromptBuilderDouble.build_ntl_prompt(self, self.config, self.source_text_dict) # 禁翻表

        self.replace_dict = {
            "{original_text}":source_text_str,
            "{previous_text}":previous_text,
            "{glossary}":glossary,
            "{code_text}":code
        }


        # 进行文本占位符替换
        messages, system_content = PromptBuilderDouble.replace_message_content(self,
            self.replace_dict,
            self.messages_a,
            self.system_prompt_a
        )

        # 获取第一次平台配置信息包
        platform_config = self.config.get_platform_configuration("doubleReqA")
        model_a = platform_config["model_name"]

        # 发起第一次请求
        requester = TranslatorRequester(self.config, self.plugin_manager)
        skip, response_think, response_content, prompt_tokens_a, completion_tokens_a = requester.sent_request(
            messages,
            system_content,
            platform_config
        )

        # 如果请求结果标记为 skip，即有运行错误发生，则直接返回错误信息，停止后续任务
        if skip == True:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }
        
        # 提取回复内容
        response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content)
        # 更新术语表与禁翻表到配置文件中
        self.config.update_glossary_ntl_config(glossary_result, NTL_result)


        # 模型回复日志
        if response_think != "":
            self.extra_log.append("第一次模型思考内容：\n" + response_think)
        if self.is_debug():
            self.extra_log.append("第一次模型回复内容：\n" + response_content)


        # 进行提取阶段,并更新替换字典
        self.replace_dict,self.extra_log = PromptBuilderDouble.process_extraction_phase(self,
            self.config, 
            self.replace_dict,
            response_think,
            response_content,
            self.extra_log
        )


        # 进行第二次文本占位符替换
        messages, system_content = PromptBuilderDouble.replace_message_content(self,
            self.replace_dict,
            self.messages_b,
            self.system_prompt_b
        )


        # 获取第二次平台配置信息包
        platform_config = self.config.get_platform_configuration("doubleReqB")
        model_b = platform_config["model_name"]

        # 发起第二次请求
        requester = TranslatorRequester(self.config, self.plugin_manager)
        skip, response_think, response_content, prompt_tokens_b, completion_tokens_b = requester.sent_request(
            messages,
            system_content,
            platform_config
        )


        # 如果请求结果标记为 skip，即有运行错误发生，则直接返回错误信息，停止后续任务
        if skip == True:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

        # 提取回复内容
        response_dict, glossary_result, NTL_result = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content)

        # 检查回复内容
        check_result, error_content = ResponseChecker.check_response_content(
            self,
            self.config.response_check_switch,
            response_content,
            response_dict,
            self.source_text_dict,
            self.config.source_language
        )

        # 模型回复日志
        if response_think != "":
            self.extra_log.append("第二次模型思考内容：\n" + response_think)
        if self.is_debug():
            self.extra_log.append("第二次模型回复内容：\n" + response_content)

        # 合并消耗和模型号
        prompt_tokens = prompt_tokens_a + prompt_tokens_b
        completion_tokens = completion_tokens_a + completion_tokens_b
        model = model_a + " and " + model_b

        # 检查译文
        if check_result == False:
            error = f"译文文本未通过检查，将在下一轮次的翻译中重新翻译 - {error_content}"

            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        error,
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        self.source_text_dict.values(),
                        response_dict.values(),
                        self.extra_log,
                    )
                )
            )
        else:
            # 各种还原步骤
            # 先复制一份，以免影响原有数据，response_dict 为字符串字典，所以浅拷贝即可
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.restore_all(restore_response_dict, self.prefix_codes, self.suffix_codes)

            # 更新译文结果到缓存数据中
            for item, response in zip(self.items, restore_response_dict.values()):
                item.set_model(model)
                item.set_translated_text(response)
                item.set_translation_status(CacheItem.STATUS.TRANSLATED)

            # 打印任务结果
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        "",
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        self.source_text_dict.values(),
                        response_dict.values(),
                        self.extra_log,
                    )
                )
            )


        # 否则返回译文检查的结果
        if check_result == False:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }
        else:
            return {
                "check_result": check_result,
                "row_count": self.row_count,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }



    # 设置缓存数据
    def set_items(self, items: list[CacheItem]) -> None:
        self.items = items

    # 设置上文数据
    def set_previous_items(self, previous_items: list[CacheItem]) -> None:
        self.previous_items = previous_items

    # 消息构建预处理
    def prepare(self, target_platform: str, prompt_preset: int) -> None:

        # 生成上文文本列表
        self.previous_text_list = [v.get_source_text() for v in self.previous_items]

        # 生成原文文本字典
        self.source_text_dict = {str(i): v.get_source_text() for i, v in enumerate(self.items)}

        # 生成文本行数信息
        self.row_count = len(self.source_text_dict)

        # 触发插件事件 - 文本正规化
        self.plugin_manager.broadcast_event("normalize_text", self.config, self.source_text_dict)

        # 各种替换步骤，译前替换，提取首位代码段
        self.source_text_dict, self.prefix_codes, self.suffix_codes = self.replace_all(self.source_text_dict, self.prefix_pattern, self.suffix_pattern)

        # 生成请求指令
        if self.config.double_request_switch_settings == True:
            self.messages_a, self.system_prompt_a = self.generate_prompt_DRA()
            self.messages_b, self.system_prompt_b = self.generate_prompt_DRB()

        elif target_platform == "sakura":
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_sakura(
                self.source_text_dict,
                self.previous_text_list,
            )
        elif target_platform == "LocalLLM":
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_LocalLLM(
                self.source_text_dict,
                self.previous_text_list,
            )
        elif prompt_preset in (PromptBuilderEnum.THINK,):
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_think(
                self.source_text_dict,
                self.previous_text_list
            )
        elif prompt_preset in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT, PromptBuilderEnum.CUSTOM):
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt(
                self.source_text_dict,
                self.previous_text_list
            )

        # 预估 Token 消费,暂时版本，双请求无法正确计算tpm与tokens消耗
        self.request_tokens_consume = self.request_limiter.calculate_tokens(
            self.messages,
            self.messages_a, 
            self.messages_b,   
            self.system_prompt,
            self.system_prompt_a,
            self.system_prompt_b
            )

    # 各种替换步骤
    def replace_all(self, text_dict: dict, prefix_pattern: re.Pattern, suffix_pattern: re.Pattern) -> tuple[dict, dict, dict]:
        # 译前替换
        if self.config.pre_translation_switch == True:
            text_dict = self.replace_before_translation(text_dict)

        # 替换 前缀代码段 和 后缀代码段
        prefix_codes = []
        suffix_codes = []
        if self.config.preserve_prefix_and_suffix_codes == True:
            text_dict, prefix_codes, suffix_codes = self.replace_prefix_and_suffix_codes(text_dict, prefix_pattern, suffix_pattern)

        return text_dict, prefix_codes, suffix_codes

    # 各种还原步骤，注意还原中各步骤的执行顺序与替换中各步骤的执行循环相反
    def restore_all(self, text_dict: dict, prefix_codes: dict, suffix_codes: dict) -> dict:

        # 还原 前缀代码段 和 后缀代码段
        if self.config.preserve_prefix_and_suffix_codes == True:
            text_dict = self.restore_prefix_and_suffix_codes(text_dict, prefix_codes, suffix_codes)

        # 译后替换
        if self.config.post_translation_switch == True:
            text_dict = self.replace_after_translation(text_dict)

        return text_dict


    # 替换 前缀代码段、后缀代码段
    def replace_prefix_and_suffix_codes(self, text_dict: dict, prefix_pattern: re.Pattern, suffix_pattern: re.Pattern) -> tuple[dict, dict, dict]:
        prefix_codes = {}
        suffix_codes = {}
        for k in text_dict:
            # 查找与替换前缀代码段
            prefix_codes[k] = prefix_pattern.findall(text_dict[k])
            text_dict[k] = prefix_pattern.sub("", text_dict[k])

            # 查找与替换后缀代码段
            suffix_codes[k] = suffix_pattern.findall(text_dict[k])
            text_dict[k] = suffix_pattern.sub("", text_dict[k])

        return text_dict, prefix_codes, suffix_codes

    # 恢复 前缀代码段、后缀代码段
    def restore_prefix_and_suffix_codes(self, text_dict: dict, prefix_codes: dict, suffix_codes: dict) -> dict:
        for k in text_dict:
            text_dict[k] = "".join(prefix_codes[k]) +  text_dict[k] + "".join(suffix_codes[k])

        return text_dict

    # 译后替换
    def replace_before_translation(self, text_dict: dict) -> dict:
        data: list[dict] = self.config.pre_translation_data

        for k in text_dict:
            for v in data:
                if v.get("src", "") in text_dict[k]:
                    text_dict[k] = text_dict[k].replace(v.get("src", ""), v.get("dst", ""))

        return text_dict

    # 译前替换
    def replace_after_translation(self, text_dict: dict) -> dict:
        data: list[dict] = self.config.post_translation_data

        for k in text_dict:
            for v in data:
                if v.get("src", "") in text_dict[k]:
                    text_dict[k] = text_dict[k].replace(v.get("src", ""), v.get("dst", ""))

        return text_dict

    # 生成指令
    def generate_prompt(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础提示词
        if self.config.prompt_preset == PromptBuilderEnum.CUSTOM:
            system = self.config.system_prompt_content
        else:
            system = PromptBuilder.build_system(self.config)

        # 如果开启自动构建术语表
        if self.config.auto_glossary_toggle == True:
            glossary_criteria = PromptBuilder.build_glossary_extraction_criteria(self.config)
            if glossary_criteria != "":
                system += glossary_criteria
                extra_log.append(glossary_criteria)

        # 如果开启自动构建禁翻表
        if self.config.auto_exclusion_list_toggle == True:
            ntl_criteria = PromptBuilder.build_ntl_extraction_criteria(self.config)
            if ntl_criteria != "":
                system += ntl_criteria
                extra_log.append(ntl_criteria)

        # 如果开启术语表
        if self.config.prompt_dictionary_switch == True:
            glossary = PromptBuilder.build_glossary_prompt(self.config, source_text_dict)
            if glossary != "":
                system += glossary
                extra_log.append(glossary)

        # 如果开启禁翻表
        if self.config.exclusion_list_switch == True:
            ntl = PromptBuilder.build_ntl_prompt(self.config, source_text_dict)
            if ntl != "":
                system += ntl
                extra_log.append(ntl)


        # 如果角色介绍开关打开
        if self.config.characterization_switch == True:
            characterization = PromptBuilder.build_characterization(self.config, source_text_dict)
            if characterization != "":
                system += characterization
                extra_log.append(characterization)

        # 如果启用自定义世界观设定功能
        if self.config.world_building_switch == True:
            world_building = PromptBuilder.build_world_building(self.config)
            if world_building != "":
                system += world_building
                extra_log.append(world_building)

        # 如果启用自定义行文措辞要求功能
        if self.config.writing_style_switch == True:
            writing_style = PromptBuilder.build_writing_style(self.config)
            if writing_style != "":
                system += writing_style
                extra_log.append(writing_style)

        # 如果启用翻译风格示例功能
        if self.config.translation_example_switch == True:
            translation_example = PromptBuilder.build_translation_example(self.config)
            if translation_example != "":
                system += translation_example
                extra_log.append(translation_example)

        # 获取默认示例前置文本
        pre_prompt = PromptBuilder.build_userExamplePrefix(self.config)
        fol_prompt = PromptBuilder.build_modelExamplePrefix(self.config)

        # 获取默认示例，并构建动态few-shot
        original_exmaple, translation_example_content = PromptBuilder.build_translation_sample(self.config, source_text_dict)
        if original_exmaple and translation_example_content:
            messages.append({
                "role": "user",
                "content": f"{pre_prompt}<textarea>\n{original_exmaple}\n</textarea>"
            })
            messages.append({
                "role": "assistant",
                "content": f"{fol_prompt}<textarea>\n{translation_example_content}\n</textarea>"
            })
            extra_log.append(f"原文示例已添加：\n{original_exmaple}")
            extra_log.append(f"译文示例已添加：\n{translation_example_content}")

        # 如果加上文，获取上文内容
        previous = ""
        if self.config.pre_line_counts and previous_text_list:
            previous = PromptBuilder.build_pre_text(self.config, previous_text_list)
            if previous != "":
                extra_log.append(f"###上文\n{"\n".join(previous_text_list)}")

        # 获取提问时的前置文本
        pre_prompt = PromptBuilder.build_userQueryPrefix(self.config)
        # 获取模型预输入回复前文
        fol_prompt = PromptBuilder.build_modelResponsePrefix(self.config)

        # 构建待翻译文本 (添加序号)
        numbered_lines = []
        for index, line in enumerate(source_text_dict.values()):
            numbered_lines.append(f"{index + 1}. {line}") # 添加序号和 "." 分隔符
        source_text_str = "\n".join(numbered_lines)
        source_text_str = f"{previous}\n{pre_prompt}<textarea>\n{source_text_str}\n</textarea>"

        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        # 构建模型预输入回复信息，deepseek-reasoner 不支持该模型预回复消息
        messages.append({"role": "assistant", "content": fol_prompt})


        return messages, system, extra_log

    # 生成指令 - 思考模型
    def generate_prompt_think(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础提示词
        if self.config.prompt_preset == PromptBuilderEnum.CUSTOM:
            system = self.config.system_prompt_content
        else:
            system = PromptBuilderThink.build_system(self.config)

        # 如果开启自动构建术语表
        if self.config.auto_glossary_toggle == True:
            glossary_criteria = PromptBuilder.build_glossary_extraction_criteria(self.config)
            if glossary_criteria != "":
                system += glossary_criteria
                extra_log.append(glossary_criteria)

        # 如果开启自动构建禁翻表
        if self.config.auto_exclusion_list_toggle == True:
            ntl_criteria = PromptBuilder.build_ntl_extraction_criteria(self.config)
            if ntl_criteria != "":
                system += ntl_criteria
                extra_log.append(ntl_criteria)

        # 如果开启术语表
        if self.config.prompt_dictionary_switch == True:
            result = PromptBuilder.build_glossary_prompt(self.config, source_text_dict)
            if result != "":
                system = system + "\n" + result
                extra_log.append(result)

        # 如果开启禁翻表
        if self.config.exclusion_list_switch == True:
            ntl = PromptBuilder.build_ntl_prompt(self.config, source_text_dict)
            if ntl != "":
                system += ntl
                extra_log.append(ntl)


        # 如果角色介绍开关打开
        if self.config.characterization_switch == True:
            characterization = PromptBuilder.build_characterization(self.config, source_text_dict)
            if characterization:
                system += characterization
                extra_log.append(characterization)

        # 如果启用自定义世界观设定功能
        if self.config.world_building_switch == True:
            world_building = PromptBuilder.build_world_building(self.config)
            if world_building:
                system += world_building
                extra_log.append(world_building)

        # 如果启用自定义行文措辞要求功能
        if self.config.writing_style_switch == True:
            writing_style = PromptBuilder.build_writing_style(self.config)
            if writing_style:
                system += writing_style
                extra_log.append(writing_style)

        # 如果启用翻译风格示例功能
        if self.config.translation_example_switch == True:
            translation_example = PromptBuilder.build_translation_example(self.config)
            if translation_example:
                system += translation_example
                extra_log.append(translation_example)


        # 如果加上文，获取上文内容
        previous = ""
        if self.config.pre_line_counts and previous_text_list:
            previous = PromptBuilder.build_pre_text(self.config, previous_text_list)
            if previous:
                extra_log.append(f"###上文\n{"\n".join(previous_text_list)}")

        # 获取提问时的前置文本
        pre_prompt = PromptBuilder.build_userQueryPrefix(self.config)


        # 构建待翻译文本
        source_text_str = "\n".join(source_text_dict.values())
        source_text_str = f"{previous}\n{pre_prompt}<textarea>\n{source_text_str}\n</textarea>"

        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        return messages, system, extra_log

    # 生成指令 Sakura
    def generate_prompt_sakura(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        system = PromptBuilderSakura.build_system(self.config)


        # 如果开启术语表
        glossary = ""
        if self.config.prompt_dictionary_switch == True:
            glossary = PromptBuilderSakura.build_glossary(self.config, source_text_dict)
            if glossary != "":
                extra_log.append(glossary)


        # 构建主要提示词
        if glossary == "":
            user_prompt = "将下面的日文文本翻译成中文：\n" + "\n".join(source_text_dict.values())
        else:
            user_prompt = (
                "根据以下术语表（可以为空）：\n" + glossary
                + "\n" + "将下面的日文文本根据对应关系和备注翻译成中文：\n" + "\n".join(source_text_dict.values())
            )

        # 构建指令列表
        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        return messages, system, extra_log

    # 生成指令 LocalLLM
    def generate_prompt_LocalLLM(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础提示词
        system = PromptBuilderLocal.build_system(self.config)

        # 指令词典
        if self.config.prompt_dictionary_switch == True:
            result = PromptBuilder.build_glossary(self.config, source_text_dict)
            if result != "":
                system = system + "\n" + result
                extra_log.append(result)

        # 如果开启禁翻表
        if self.config.exclusion_list_switch == True:
            ntl = PromptBuilder.build_ntl_prompt(self.config, source_text_dict)
            if ntl != "":
                system += ntl
                extra_log.append(ntl)

        # 构建待翻译文本
        numbered_lines = []
        for index, line in enumerate(source_text_dict.values()):
            numbered_lines.append(f"{index + 1}. {line}") # 添加序号和 "." 分隔符
        source_text_str = "\n".join(numbered_lines)
        source_text_str = f"<textarea>\n{source_text_str}\n</textarea>"

        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )


        return messages, system, extra_log

    # 构造通用信息结构 第一次请求
    def generate_prompt_DRA(self):
        """构建通用消息结构"""

        # 获取流程设计配置
        request_cards = self.config.flow_design_list["request_phase_a"]

        messages = []
        system_content = ""

        for card in request_cards:
            if card["type"] == "DialogueFragmentCard":
                settings = card["settings"]
                role_mapping = {
                    "系统": "system",
                    "用户": "user",
                    "模型": "assistant"
                }

                role = role_mapping.get(settings["role"], "user")
                content = settings["content"]


                # 记录系统消息
                if role == "system":
                    system_content = content

                # 只在角色不是 "system" 时才添加到 messages 列表
                if role != "system":
                    messages.append({
                        "role": role,
                        "content": content
                    })
                settings["system_info"] = content 


        return messages, system_content

    # 构造通用信息结构 第二次请求
    def generate_prompt_DRB(self):
        """构建通用消息结构"""

        # 获取流程设计配置
        request_cards = self.config.flow_design_list["request_phase_b"]

        messages = []
        system_content = ""

        for card in request_cards:
            if card["type"] == "DialogueFragmentCard":
                settings = card["settings"]
                role_mapping = {
                    "系统": "system",
                    "用户": "user",
                    "模型": "assistant"
                }

                role = role_mapping.get(settings["role"], "user")
                content = settings["content"]


                # 记录系统消息
                if role == "system":
                    system_content = content

                # 只在角色不是 "system" 时才添加到 messages 列表
                if role != "system":
                    messages.append({
                        "role": role,
                        "content": content
                    })
                settings["system_info"] = content 

        return messages, system_content

    # 更新系统提示词的术语表内容(因为是特殊处理的补丁，很多判断要重新加入，后续提示词相关更新需要重点关注该函数，以免bug)
    def update_sysprompt_glossary(self,config,system_prompt, prompt_dictionary_data, source_text_dict):

        # 应用开关检查
        if config.prompt_dictionary_switch == False:
            return system_prompt
        
        # 本地接口不适用
        if config.target_platform == "sakura":
            return system_prompt

        if config.target_platform == "LocalLLM":
            return system_prompt


        # 生成符合条件的术语条目
        entries = []
        for item in prompt_dictionary_data:
            src = item.get("src", "")
            # 检查原文是否在任意源文本中出现
            if any(src in text for text in source_text_dict.values()):
                dst = item.get("dst", "")
                info = item.get("info", "")
                entries.append(f"{src}|{dst}|{info}")
        
        # 构建新术语表
        if config.target_language in ("简中", "繁中"):
            term_table = "###术语表\n原文|译文|备注"
        else:
            term_table = "###Glossary\nOriginal Text|Translation|Remarks"
        if entries:
            term_table += "\n" + "\n".join(entries)
            term_table += "\n\n"
        else:
            return system_prompt
        
        # 处理系统提示
        if "###术语表" in system_prompt:
            # 正则匹配术语表区块（含标题行）
            pattern = r'###术语表[^\#]*'
            return re.sub(pattern, term_table, system_prompt, flags=re.DOTALL)
        
        elif "###Glossary" in system_prompt:
            # 正则匹配术语表区块（含标题行）
            pattern = r'###Glossary[^\#]*'
            return re.sub(pattern, term_table, system_prompt, flags=re.DOTALL)
        
        else:
            # 直接拼接新术语表
            delimiter = "\n" if system_prompt and not system_prompt.endswith("\n") else ""
            return f"{system_prompt}{delimiter}\n{term_table}"


    # 生成日志行
    def generate_log_rows(self, error: str, start_time: int, prompt_tokens: int, completion_tokens: int, source: list[str], translated: list[str], extra_log: list[str]) -> tuple[list[str], bool]:
        rows = []

        if error != "":
            rows.append(error)
        else:
            rows.append(
                f"任务耗时 {(time.time() - start_time):.2f} 秒，"
                + f"文本行数 {len(source)} 行，指令消耗 {prompt_tokens} Tokens，补全消耗 {completion_tokens} Tokens"
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
    def generate_log_table(self, rows: list, success: bool) -> Table:
        table = Table(
            box = box.ASCII2,
            expand = True,
            title = " ",
            caption = " ",
            highlight = True,
            show_lines = True,
            show_header = False,
            show_footer = False,
            collapse_padding = True,
            border_style = "green" if success else "red",
        )
        table.add_column("", style = "white", ratio = 1, overflow = "fold")

        for row in rows:
            if isinstance(row, str):
                table.add_row(row)
            else:
                table.add_row(*row)

        return table
    
