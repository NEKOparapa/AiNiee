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
from ModuleFolders.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal
from ModuleFolders.PromptBuilder.PromptBuilderSakura import PromptBuilderSakura
from ModuleFolders.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.RequestLimiter.RequestLimiter import RequestLimiter

from ModuleFolders.TextProcessor.TextProcessor import TextProcessor


class TranslatorTask(Base):

    def __init__(self, config: TaskConfig, plugin_manager: PluginManager, request_limiter: RequestLimiter, source_lang) -> None:
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
                self.source_lang, 
                self.source_text_dict
            )
        
        # 生成请求指令
        if target_platform == "sakura":
            self.messages, self.system_prompt, self.extra_log = PromptBuilderSakura.generate_prompt_sakura(
                self.config,
                self.source_text_dict,
                self.previous_text_list, 
                self.source_lang, 
            )
        elif target_platform == "LocalLLM":
            self.messages, self.system_prompt, self.extra_log = PromptBuilderLocal.generate_prompt_LocalLLM(
                self.config,
                self.source_text_dict,
                self.previous_text_list,
                self.source_lang,
            )
        else:
            self.messages, self.system_prompt, self.extra_log = PromptBuilder.generate_prompt(
                self.config,
                self.source_text_dict,
                self.previous_text_list,
                self.source_lang,
            )

        # 预估 Token 消费
        self.request_tokens_consume = self.request_limiter.calculate_tokens(self.messages,self.system_prompt,)


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

        # 返空判断
        if response_content is None or not response_content.strip():
            error = "API请求错误，模型回复内容为空，将在下一轮次重试"
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        error,
                        task_start_time,
                        prompt_tokens if prompt_tokens is not None else self.request_tokens_consume,
                        0,
                        [],  
                        [], 
                        []   
                    )
                )
            )
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
