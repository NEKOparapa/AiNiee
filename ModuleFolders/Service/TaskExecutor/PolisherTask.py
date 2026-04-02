import copy
import itertools
import re
import time

from rich import box
from rich.markup import escape
from rich.table import Table

from ModuleFolders.Base.Base import Base
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.Plugin.PluginManager import PluginManager
from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Domain.PromptBuilder.PromptBuilderPolishing import PromptBuilderPolishing
from ModuleFolders.Domain.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.Domain.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.Infrastructure.RequestLimiter.RequestLimiter import RequestLimiter
from ModuleFolders.Infrastructure.Tokener.Tokener import Tokener
from ModuleFolders.Domain.TextProcessor.PolishTextProcessor import PolishTextProcessor


class PolisherTask(LogMixin, Base):

    def __init__(self, config: TaskConfig, plugin_manager: PluginManager, request_limiter: RequestLimiter) -> None:
        super().__init__()

        self.config = config
        self.plugin_manager = plugin_manager
        self.request_limiter = request_limiter
        self.text_processor = PolishTextProcessor(self.config)

        self.messages = []
        self.system_prompt = ""
        self.extra_log = []

    def set_items(self, items: list[CacheItem]) -> None:
        self.items = items

    def set_previous_items(self, previous_items: list[CacheItem]) -> None:
        self.previous_items = previous_items

    def prepare(self) -> None:
        self.previous_text_list = [item.source_text for item in self.previous_items]
        self.source_text_dict = {str(i): item.source_text for i, item in enumerate(self.items)}
        self.translation_text_dict = {str(i): item.translated_text for i, item in enumerate(self.items)}
        self.row_count = len(self.source_text_dict)

        self.source_text_dict = self.text_processor.replace_all(self.config, self.source_text_dict)
        self.translation_text_dict = self.text_processor.replace_all(self.config, self.translation_text_dict)

        self.messages, self.system_prompt, self.extra_log = PromptBuilderPolishing.generate_prompt(
            self.config,
            self.source_text_dict,
            self.translation_text_dict,
            self.previous_text_list,
        )

        self.request_tokens_consume = Tokener.calculate_tokens(self, self.messages, self.system_prompt)

    def start(self) -> dict:
        return self.unit_polish_task()

    def unit_polish_task(self) -> dict:
        task_start_time = time.time()

        while True:
            if Base.work_status == Base.STATUS.STOPING:
                return {}

            if time.time() - task_start_time >= self.config.request_timeout:
                return {}

            if self.request_limiter.check_limiter(self.request_tokens_consume):
                break

            time.sleep(1)

        platform_config = self.config.get_platform_configuration("polishingReq")

        requester = LLMRequester()
        skip, response_think, response_content, prompt_tokens, completion_tokens = requester.sent_request(
            self.messages,
            self.system_prompt,
            platform_config,
        )

        if skip:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

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
                        [],
                    )
                )
            )
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

        text_dict = self.translation_text_dict
        response_dict = ResponseExtractor.text_extraction(self, text_dict, response_content)
        check_result, error_content = ResponseChecker.check_polish_response_content(
            self,
            self.config,
            response_content,
            response_dict,
            text_dict,
        )
        response_dict = ResponseExtractor.remove_numbered_prefix(self, response_dict)

        if response_think:
            self.extra_log.append("模型思考内容：\n" + response_think)
        if self.is_debug():
            self.extra_log.append("模型回复内容：\n" + response_content)

        if check_result is False:
            error = f"润色文本未通过检查，将在下一轮次的润色中重新处理 - {error_content}"
            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        error,
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        text_dict.values(),
                        response_dict.values(),
                        self.extra_log,
                    )
                )
            )
        else:
            restore_response_dict = copy.copy(response_dict)
            restore_response_dict = self.text_processor.restore_all(self.config, restore_response_dict)

            for item, response in zip(self.items, restore_response_dict.values()):
                with item.atomic_scope():
                    item.model = self.config.model
                    item.polished_text = response
                    item.translation_status = TranslationStatus.POLISHED

            self.print(
                self.generate_log_table(
                    *self.generate_log_rows(
                        "",
                        task_start_time,
                        prompt_tokens,
                        completion_tokens,
                        text_dict.values(),
                        response_dict.values(),
                        self.extra_log,
                    )
                )
            )

        if check_result is False:
            return {
                "check_result": False,
                "row_count": 0,
                "prompt_tokens": self.request_tokens_consume,
                "completion_tokens": 0,
            }

        return {
            "check_result": check_result,
            "row_count": self.row_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }

    def generate_log_rows(
        self,
        error: str,
        start_time: int,
        prompt_tokens: int,
        completion_tokens: int,
        source: list[str],
        translated: list[str],
        extra_log: list[str],
    ) -> tuple[list[str], bool]:
        rows = []

        if error != "":
            rows.append(error)
        else:
            rows.append(
                f"任务耗时 {(time.time() - start_time):.2f} 秒，"
                + f"文本行数 {len(source)} 行，提示消耗 {prompt_tokens} Tokens，补全消耗 {completion_tokens} Tokens"
            )

        for item in extra_log:
            rows.append(item.strip())

        pair = ""
        for source_text, translated_text in itertools.zip_longest(source, translated, fillvalue=""):
            pair += "\n"
            source_lines = source_text.split("\n") if source_text is not None else [""]
            translated_lines = translated_text.split("\n") if translated_text is not None else [""]
            for source_line, translated_line in itertools.zip_longest(source_lines, translated_lines, fillvalue=""):
                pair += f"{source_line} [bright_blue]-->[/] {translated_line}\n"

        rows.append(pair.strip())

        return rows, error == ""

    def generate_log_table(self, rows: list, success: bool) -> Table:
        table = Table(
            box=box.ASCII2,
            expand=True,
            title=" ",
            caption=" ",
            highlight=True,
            show_lines=True,
            show_header=False,
            show_footer=False,
            collapse_padding=True,
            border_style="green" if success else "red",
        )
        table.add_column("", style="white", ratio=1, overflow="fold")

        for row in rows:
            if isinstance(row, str):
                table.add_row(escape(row, re.compile(r"(\\*)(\[(?!bright_blue\]|\/\])[a-z#/@][^[]*?)").sub))
            else:
                table.add_row(*row)

        return table
