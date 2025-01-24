import copy
import re
import time
import itertools

import rapidjson as json
from rich import box
from rich.table import Table

from Base.Base import Base
from Base.PluginManager import PluginManager
from Module_Folders.PromptBuilder.PromptBuild import PromptBuilder
from Module_Folders.Cache.CacheItem import CacheItem
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig
from Module_Folders.Translator.TranslatorRequester import TranslatorRequester
from Module_Folders.Response_Parser.Response import Response_Parser
from Module_Folders.Request_Limiter.Request_limit import Request_Limiter

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

    def __init__(self, config: TranslatorConfig, plugin_manager: PluginManager, request_limiter: Request_Limiter) -> None:
        super().__init__()

        # 初始化
        self.config = config
        self.plugin_manager = plugin_manager
        self.request_limiter = request_limiter

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
        return self.request(False)

    # 请求
    def request(self, degradation_flag: bool) -> dict:
        # 任务开始的时间
        task_start_time = time.time()

        while True:
            # 检测是否需要停止任务
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

        # 发起请求
        requester = TranslatorRequester(self.config, self.plugin_manager)
        skip, response_str, prompt_tokens, completion_tokens, response_think = requester.request(self.messages, self.system_prompt, degradation_flag)
        # 如果请求结果标记为 skip，即有错误发生，则跳过本次循环
        if skip == True:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

        # 提取回复内容
        response_dict = Response_Parser.text_extraction(self, response_str)

        # 检查回复内容
        check_result, error_content = Response_Parser.check_response_content(
            self,
            self.config.reply_check_switch,
            response_str,
            response_dict,
            self.source_text_dict,
            self.config.source_language
        )

        # 检查译文
        retry_flag = False
        if check_result == False:
            # 如果检查到模型退化，并且本次任务中退化标识为 False，则将重试标识设置为 True
            if "退化" in error_content and degradation_flag == False:
                error = "译文文本中检查到模型退化现象，正在重试"
                retry_flag = True
            # 如果检查到模型退化，并且本次任务中退化标识为 True，则放弃本次任务
            elif "退化" in error_content and degradation_flag == True:
                error = "译文文本中检查到模型退化现象，将在下一轮次的翻译中重新翻译"
            else:
                error = f"译文文本未通过检查，将在下一轮次的翻译中重新翻译 - {error_content}"

            # 打印任务结果
            if self.config.switch_debug_mode:
                response_think_log = "[AI思考过程]\n"  + response_think
                response_str_log = "[AI回复内容]\n"  + response_str

                self.extra_log.append(response_think_log)
                self.extra_log.append(response_str_log)

            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        "",
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        self.source_text_dict.values(),
                        response_dict.values(),
                        self.extra_log
                    )
                )
            )

        else:
            # 各种还原步骤
            # 先复制一份，以免影响原有数据，response_dict 为字符串字典，所以浅拷贝即可
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.restore_all(restore_response_dict, self.prefix_codes, self.suffix_codes)

            # 更新缓存数据
            for item, response in zip(self.items, restore_response_dict.values()):
                item.set_model(self.config.model)
                item.set_translated_text(response)
                item.set_translation_status(CacheItem.STATUS.TRANSLATED)

            # 打印任务结果
            if self.config.switch_debug_mode:
                response_think_log = "[AI思考过程]\n"  + response_think
                response_str_log = "[AI回复内容]\n"  + response_str

                self.extra_log.append(response_think_log)
                self.extra_log.append(response_str_log)

            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        "",
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        self.source_text_dict.values(),
                        response_dict.values(),
                        self.extra_log
                    )
                )
            )




        # 当重试标识为 True 时，重新发起请求
        # 否则返回译文检查的结果
        if retry_flag == True:
            return self.request(True)
        elif check_result == False:
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

    # 预处理
    def prepare(self, target_platform: str, api_format: str) -> None:
        # 生成上文文本列表
        self.previous_text_list = [v.get_source_text() for v in self.previous_items]

        # 生成原文文本字典
        self.source_text_dict = {str(i): v.get_source_text() for i, v in enumerate(self.items)}

        # 生成文本行数信息
        self.row_count = len(self.source_text_dict)

        # 触发插件事件 - 文本正规化
        self.plugin_manager.broadcast_event("normalize_text", self.config, self.source_text_dict)

        # 各种替换步骤
        self.source_text_dict, self.prefix_codes, self.suffix_codes = self.replace_all(self.source_text_dict, self.prefix_pattern, self.suffix_pattern)

        # 生成请求指令
        if target_platform == "sakura":
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_sakura(
                self.source_text_dict,
                self.previous_text_list,
            )
        else:
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt(
                target_platform,
                api_format,
                self.source_text_dict,
                self.previous_text_list
            )

        # 预估 Token 消费，并检查 RPM 和 TPM 限制
        self.request_tokens_consume = self.request_limiter.num_tokens_from_messages(self.messages)

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

        # 替换 换行符
        if self.config.preserve_line_breaks_toggle == True:
            text_dict = self.replace_line_breaks(text_dict)

        return text_dict, prefix_codes, suffix_codes

    # 各种还原步骤，注意还原中各步骤的执行顺序与替换中各步骤的执行循环相反
    def restore_all(self, text_dict: dict, prefix_codes: dict, suffix_codes: dict) -> dict:
        # 还原 换行符
        if self.config.preserve_line_breaks_toggle == True:
            text_dict = self.restore_line_breaks(text_dict)

        # 还原 前缀代码段 和 后缀代码段
        if self.config.preserve_prefix_and_suffix_codes == True:
            text_dict = self.restore_prefix_and_suffix_codes(text_dict, prefix_codes, suffix_codes)

        # 译后替换
        if self.config.post_translation_switch == True:
            text_dict = self.replace_after_translation(text_dict)

        return text_dict

    # 替换换行符
    def replace_line_breaks(self, text_dict: dict) -> dict:
        for k in text_dict:
            text_dict[k] = text_dict[k].replace("\n", "＠").replace("\r", "∞")

        return text_dict

    # 还原换行符
    def restore_line_breaks(self, text_dict: dict) -> dict:
        for k in text_dict:
            text_dict[k] = text_dict[k].replace("@", "\n").replace("＠", "\n").replace("∞", "\r")

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

    # 译前替换
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
    def generate_prompt(self, target_platform: str, api_format: str, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 获取基础系统提示词
        system_prompt = PromptBuilder.get_system_prompt(self.config)

        # 如果开启指令词典
        glossary = ""
        glossary_cot = ""
        if self.config.prompt_dictionary_switch:
            glossary, glossary_cot = PromptBuilder.build_glossary_prompt(self.config, source_text_dict)
            if glossary:
                system_prompt += glossary
                extra_log.append(f"指令词典已添加：\n{glossary}")

        # 如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if self.config.characterization_switch:
            characterization, characterization_cot = PromptBuilder.build_characterization(self.config, source_text_dict)
            if characterization:
                system_prompt += characterization
                extra_log.append(f"角色介绍已添加：\n{characterization}")

        # 如果启用自定义世界观设定功能
        world_building = ""
        world_building_cot = ""
        if self.config.world_building_switch:
            world_building, world_building_cot = PromptBuilder.build_world(self.config)
            if world_building:
                system_prompt += world_building
                extra_log.append(f"世界观设定已添加：\n{world_building}")

        # 如果启用自定义行文措辞要求功能
        writing_style = ""
        writing_style_cot = ""
        if self.config.writing_style_switch:
            writing_style, writing_style_cot = PromptBuilder.build_writing_style(self.config)
            if writing_style:
                system_prompt += writing_style
                extra_log.append(f"行文措辞要求已添加：\n{writing_style}")


        # 如果启用翻译风格示例功能
        if self.config.translation_example_switch:
            translation_example = PromptBuilder.build_translation_example(self.config)
            if translation_example:
                system_prompt += translation_example
                extra_log.append(f"翻译示例已添加：\n{translation_example}")


        # 获取默认示例前置文本
        pre_prompt = PromptBuilder.build_userExamplePrefix(self.config)
        fol_prompt = PromptBuilder.build_modelExamplePrefix(
            self.config,
            glossary_cot,
            characterization_cot,
            world_building_cot,
            writing_style_cot
        )

        # 获取默认示例，并构建动态few-shot
        original_exmaple, translation_example_content = PromptBuilder.build_translation_sample(self.config, source_text_dict)
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

        # 如果加上文，获取上文内容
        previous = ""
        if self.config.pre_line_counts and previous_text_list:
            previous = PromptBuilder.build_pre_text(self.config, previous_text_list)
            if previous:
                extra_log.append(f"参考上文已添加：\n{"\n".join(previous_text_list)}")

        # 获取提问时的前置文本
        pre_prompt = PromptBuilder.build_userQueryPrefix(self.config)
        # 获取模型预输入回复前文
        fol_prompt = PromptBuilder.build_modelResponsePrefix(self.config)

        # 构建待翻译文本
        source_text_str = json.dumps(source_text_dict, ensure_ascii = False)
        source_text_str = f"{previous}\n{pre_prompt}```json\n{source_text_str}\n```"

        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        # 构建模型预输入回复信息
        messages.append(
        {
            "role": "assistant",
            "content": fol_prompt
        }
        )  #deepseek-reasoner不支持该模型预回复消息

        # 当目标为 google 系列接口时，转换 messages 的格式
        # 当目标为 anthropic 兼容接口时，保持原样
        # 当目标为其他接口时，即openai接口，添加系统指令
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
    def generate_prompt_sakura(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存额外日志
        extra_log = []
        # 储存主体指令
        messages = []

        # 构建系统提示词
        messages.append({
            "role": "system",
            "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"
        })

        # 如果开启了携带上文功能
        if self.config.pre_line_counts and previous_text_list:
            messages.append({
                "role": "user",
                "content": "将下面的日文文本翻译成中文：" + "\n".join(previous_text_list),
            })
            extra_log.append(f"参考上文已添加：\n{"\n".join(previous_text_list)}")

        # 如果开启了指令词典功能
        gpt_dict_raw_text = ""
        if self.config.prompt_dictionary_switch:
            glossary_prompt = PromptBuilder.build_glossary_prompt_sakura(self.config, source_text_dict)
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

        # 原文数据为 字典，将其转换为多行字符串
        source_text_str = "\n".join(source_text_dict.values())

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