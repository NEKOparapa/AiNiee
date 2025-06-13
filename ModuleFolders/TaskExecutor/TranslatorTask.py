import copy
import re
import time
import itertools

from rich import box
from rich.table import Table
from rich.markup import escape

from Base.Base import Base
from Base.PluginManager import PluginManager
from ModuleFolders.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.TaskExecutor import TaskExecutor
from ModuleFolders.TaskExecutor.TaskConfig import TaskConfig
from ModuleFolders.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal
from ModuleFolders.PromptBuilder.PromptBuilderSakura import PromptBuilderSakura
from ModuleFolders.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.RequestLimiter.RequestLimiter import RequestLimiter

from ModuleFolders.TextProcessor.TextProcessor import TextProcessor


class TranslatorTask(Base):

    def __init__(self, config: TaskConfig, plugin_manager: PluginManager, request_limiter: RequestLimiter, source_lang: "TaskExecutor.SourceLang") -> None:
        super().__init__()

        self.config = config
        self.plugin_manager = plugin_manager
        self.request_limiter = request_limiter
        self.text_processor = TextProcessor(self.config) # 文本处理器

        # 源语言对象
        self.source_lang = source_lang

        # 提示词与信息内容存储
        self.messages = []
        self.system_prompt = ""

        # 输出日志存储
        self.extra_log = []
        # 前后缀处理信息存储
        self.prefix_codes = {}
        self.suffix_codes = {}
        # 占位符顺序存储结构
        self.placeholder_order = {}
        # 前后换行空格处理信息存储
        self.affix_whitespace_storage = {}


    # 设置缓存数据
    def set_items(self, items: list[CacheItem]) -> None:
        self.items = items

    # 设置上文数据
    def set_previous_items(self, previous_items: list[CacheItem]) -> None:
        self.previous_items = previous_items

    # 消息构建预处理
    def prepare(self, target_platform: str) -> None:

        # 生成上文文本列表
        self.previous_text_list = [v.source_text for v in self.previous_items]

        # 生成原文文本字典
        self.source_text_dict = {str(i): v.source_text for i, v in enumerate(self.items)}

        # 生成文本行数信息
        self.row_count = len(self.source_text_dict)

        # 触发插件事件 - 文本正规化
        self.plugin_manager.broadcast_event("normalize_text", self.config, self.source_text_dict)

        # 各种替换步骤，译前替换，提取首尾与占位中间代码
        self.source_text_dict, self.prefix_codes, self.suffix_codes, self.placeholder_order, self.affix_whitespace_storage = \
            self.text_processor.replace_all(
                self.config,
                self.source_lang.new, 
                self.source_text_dict
            )
        
        # 生成请求指令
        if target_platform == "sakura":
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_sakura(
                self.source_text_dict,
                self.previous_text_list,
            )
        elif target_platform == "LocalLLM":
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt_LocalLLM(
                self.source_text_dict,
                self.previous_text_list,
            )
        else:
            self.messages, self.system_prompt, self.extra_log = self.generate_prompt(
                self.source_text_dict,
                self.previous_text_list,
            )

        # 预估 Token 消费
        self.request_tokens_consume = self.request_limiter.calculate_tokens(self.messages,self.system_prompt,)

    # 生成信息结构 - 通用
    def generate_prompt(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础系统提示词
        if self.config.translation_prompt_selection["last_selected_id"] in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT, PromptBuilderEnum.THINK):
            system = PromptBuilder.build_system(self.config, self.source_lang.new)
        else:
            system = self.config.translation_prompt_selection["prompt_content"]  # 自定义提示词


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

        # 构建动态few-shot
        switch_A = self.config.few_shot_and_example_switch # 打开动态示例开关时
        switch_B = self.config.translation_prompt_selection["last_selected_id"] == PromptBuilderEnum.COMMON #仅在通用提示词
        if switch_A and switch_B:

            # 获取默认示例前置文本
            pre_prompt_example = PromptBuilder.build_userExamplePrefix(self.config)
            fol_prompt_example = PromptBuilder.build_modelExamplePrefix(self.config)

            # 获取具体动态示例内容
            original_exmaple, translation_example_content = PromptBuilder.build_translation_sample(self.config, source_text_dict, self.source_lang)
            if original_exmaple and translation_example_content:
                messages.append({
                    "role": "user",
                    "content": f"{pre_prompt_example}<textarea>\n{original_exmaple}\n</textarea>"
                })
                messages.append({
                    "role": "assistant",
                    "content": f"{fol_prompt_example}<textarea>\n{translation_example_content}\n</textarea>"
                })
                extra_log.append(f"原文示例已添加：\n{original_exmaple}")
                extra_log.append(f"译文示例已添加：\n{translation_example_content}")

        # 如果加上文，获取上文内容
        previous = ""
        if self.config.pre_line_counts and previous_text_list:
            previous = PromptBuilder.build_pre_text(self.config, previous_text_list)
            if previous != "":
                extra_log.append(f"###上文内容\n{"\n".join(previous_text_list)}")


        # 构建待翻译文本
        source_text = PromptBuilder.build_source_text(self.config,source_text_dict)
        pre_prompt = PromptBuilder.build_userQueryPrefix(self.config) # 用户提问前置文本
        source_text_str = f"{previous}\n{pre_prompt}<textarea>\n{source_text}\n</textarea>"

        # 构建用户信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        # 构建预输入回复信息
        switch_C = self.config.translation_prompt_selection["last_selected_id"] in (PromptBuilderEnum.COT, PromptBuilderEnum.COMMON) 
        if switch_A and switch_C:
            fol_prompt = PromptBuilder.build_modelResponsePrefix(self.config)
            messages.append({"role": "assistant", "content": fol_prompt})


        return messages, system, extra_log

    # 生成信息结构 - Sakura
    def generate_prompt_sakura(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        system = PromptBuilderSakura.build_system(self.config, self.source_lang.new)


        # 如果开启术语表
        glossary = ""
        if self.config.prompt_dictionary_switch == True:
            glossary = PromptBuilderSakura.build_glossary(self.config, source_text_dict)
            if glossary != "":
                extra_log.append(glossary)

        # 构建待翻译文本
        source_text = PromptBuilder.build_source_text(self.config,source_text_dict)

        # 构建主要提示词
        if glossary == "":
            user_prompt = "将下面的日文文本翻译成中文：\n" + source_text
        else:
            user_prompt = (
                "根据以下术语表（可以为空）：\n" + glossary
                + "\n" + "将下面的日文文本根据对应关系和备注翻译成中文：\n" + source_text
            )

        # 构建指令列表
        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        return messages, system, extra_log

    # 生成信息结构 - LocalLLM
    def generate_prompt_LocalLLM(self, source_text_dict: dict, previous_text_list: list[str]) -> tuple[list[dict], str, list[str]]:
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []

        # 基础提示词
        system = PromptBuilderLocal.build_system(self.config, self.source_lang.new)

        # 术语表
        if self.config.prompt_dictionary_switch == True:
            result = PromptBuilder.build_glossary_prompt(self.config, source_text_dict)
            if result != "":
                system = system + "\n" + result
                extra_log.append(result)
        
        # 构建待翻译文本
        source_text = PromptBuilder.build_source_text(self.config,source_text_dict)
        pre_prompt = PromptBuilder.build_userQueryPrefix(self.config) # 用户提问前置文本
        source_text_str = f"{pre_prompt}<textarea>\n{source_text}\n</textarea>"


        # 构建用户提问信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )


        return messages, system, extra_log

    # 启动任务
    def start(self) -> dict:
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
        platform_config = self.config.get_platform_configuration("translationReq")

        # 发起请求
        requester = LLMRequester()
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
        response_dict = ResponseExtractor.text_extraction(self, self.source_text_dict, response_content)

        # 检查回复内容
        check_result, error_content = ResponseChecker.check_response_content(
            self,
            self.config,
            self.placeholder_order,
            response_content,
            response_dict,
            self.source_text_dict,
            self.source_lang
        )

        # 去除回复内容的数字序号
        response_dict = ResponseExtractor.remove_numbered_prefix(self, response_dict)


        # 模型回复日志
        if response_think:
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
            # 各种翻译后处理
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.text_processor.restore_all(self.config, restore_response_dict, self.prefix_codes, self.suffix_codes, self.placeholder_order, self.affix_whitespace_storage)

            # 更新译文结果到缓存数据中
            for item, response in zip(self.items, restore_response_dict.values()):
                with item.atomic_scope():
                    item.model = self.config.model
                    item.translated_text = response
                    item.translation_status = TranslationStatus.TRANSLATED


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


    # 生成日志行
    def generate_log_rows(self, error: str, start_time: int, prompt_tokens: int, completion_tokens: int, source: list[str], translated: list[str], extra_log: list[str]) -> tuple[list[str], bool]:
        rows = []

        if error != "":
            rows.append(error)
        else:
            rows.append(
                f"任务耗时 {(time.time() - start_time):.2f} 秒，"
                + f"文本行数 {len(source)} 行，提示消耗 {prompt_tokens} Tokens，补全消耗 {completion_tokens} Tokens"
            )

        # 添加额外日志
        for v in extra_log:
            rows.append(v.strip())

        # 原文译文对比
        pair = ""
        # 修复变量名冲突问题，将循环变量改为 s 和 t
        for idx, (s, t) in enumerate(itertools.zip_longest(source, translated, fillvalue=""), 1):
            pair += f"\n"
            # 处理原文和译文的换行，分割成多行
            s_lines = s.split('\n') if s is not None else ['']
            t_lines = t.split('\n') if t is not None else ['']
            # 逐行对比，确保对齐
            for s_line, t_line in itertools.zip_longest(s_lines, t_lines, fillvalue=""):
                pair += f"{s_line} [bright_blue]-->[/] {t_line}\n"
        
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
                table.add_row(escape(row, re.compile(r"(\\*)(\[(?!bright_blue\]|\/\])[a-z#/@][^[]*?)").sub)) # 修复rich table不显示[]内容问题
            else:
                table.add_row(*row)

        return table
