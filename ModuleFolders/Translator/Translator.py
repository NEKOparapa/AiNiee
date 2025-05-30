import json
import os
import time
import threading
import concurrent.futures
from dataclasses import dataclass
from typing import Iterator

import opencc
from tqdm import tqdm

from Base.Base import Base
from Base.PluginManager import PluginManager
from ModuleFolders.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Cache.CacheManager import CacheManager
from ModuleFolders.Cache.CacheProject import CacheProjectStatistics
from ModuleFolders.Translator import TranslatorUtil
from ModuleFolders.Translator.TranslatorTask import TranslatorTask
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilderThink import PromptBuilderThink
from ModuleFolders.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal
from ModuleFolders.PromptBuilder.PromptBuilderSakura import PromptBuilderSakura
from ModuleFolders.FileReader.FileReader import FileReader
from ModuleFolders.FileOutputer.FileOutputer import FileOutputer
from ModuleFolders.RequestLimiter.RequestLimiter import RequestLimiter
from ModuleFolders.Translator.TranslatorUtil import get_most_common_language


@dataclass
class SourceLang:
    new: str
    most_common: str


# 翻译器
class Translator(Base):

    def __init__(self, plugin_manager: PluginManager, file_reader: FileReader, file_writer: FileOutputer) -> None:
        super().__init__()

        # 初始化
        self.plugin_manager = plugin_manager
        self.config = TranslatorConfig()
        self.cache_manager = CacheManager()
        self.request_limiter = RequestLimiter()
        self.file_reader = file_reader
        self.file_writer = file_writer

        # 注册事件
        self.subscribe(Base.EVENT.TRANSLATION_STOP, self.translation_stop)
        self.subscribe(Base.EVENT.TRANSLATION_START, self.translation_start)
        self.subscribe(Base.EVENT.TRANSLATION_MANUAL_EXPORT, self.translation_manual_export)
        self.subscribe(Base.EVENT.TRANSLATION_CONTINUE_CHECK, self.translation_continue_check)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)

    # 应用关闭事件
    def app_shut_down(self, event: int, data: dict) -> None:
        Base.work_status = Base.STATUS.STOPING

    # 翻译停止事件
    def translation_stop(self, event: int, data: dict) -> None:
        # 设置运行状态为停止中
        Base.work_status = Base.STATUS.STOPING

        def target() -> None:
            while True:
                time.sleep(0.5)
                if self.translating == False:
                    self.print("")
                    self.info("翻译任务已停止 ...")
                    self.print("")
                    self.emit(Base.EVENT.TRANSLATION_STOP_DONE, {})
                    break

        threading.Thread(target = target).start()

    # 翻译开始事件
    def translation_start(self, event: int, data: dict) -> None:
        threading.Thread(
            target = self.translation_start_target,
            args = (data.get("continue_status"),),
        ).start()

    # 翻译结果手动导出事件
    def translation_manual_export(self, event: int, data: dict) -> None:
        # 确保当前状态为 翻译中
        if Base.work_status != Base.STATUS.TRANSLATING:
            return None

        # 触发手动导出插件事件
        self.plugin_manager.broadcast_event("manual_export", self.config, self.cache_manager.project)

        # 如果开启了转换简繁开关功能，则进行文本转换
        if self.config.response_conversion_toggle:
            self.convert_simplified_and_traditional(self.config.opencc_preset, self.cache_manager.project.items_iter())
            self.print("")
            self.info(f"已启动自动简繁转换功能，正在使用 {self.config.opencc_preset} 配置进行字形转换 ...")
            self.print("")

        # 写入文件
        self.file_writer.output_translated_content(
            self.cache_manager.project,
            self.config.label_output_path,
            self.config.label_input_path,
        )

    # 继续翻译状态检查事件
    def translation_continue_check(self, event: int, data: dict) -> None:
        threading.Thread(
            target = self.translation_continue_check_target
        ).start()

    # 继续翻译状态检查
    def translation_continue_check_target(self) -> None:
        # 等一下，等页面切换效果结束再执行，避免争抢 CPU 资源，导致 UI 卡顿
        time.sleep(0.5)

        # 检查结果的默认值
        continue_status = False

        # 只有翻译状态为 无任务 时才执行检查逻辑，其他情况直接返回默认值
        if Base.work_status == Base.STATUS.IDLE:
            config = self.load_config()

            # 过渡方案，通过状态数据小文件来判断
            continue_status = self.check_project_statistics(config.get("label_output_path", ""))

        self.emit(Base.EVENT.TRANSLATION_CONTINUE_CHECK_DONE, {
            "continue_status" : continue_status,
        })

    # 继续翻译状态判断方法
    def check_project_statistics(self, folder_path: str) -> bool:

        cache_folder_path = os.path.join(folder_path, "cache")

        if not os.path.isdir(cache_folder_path):
            return False

        json_file_path = os.path.join(cache_folder_path, "ProjectStatistics.json")
        if not os.path.isfile(json_file_path):
            return False

        # 获取小文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        total_line = data["total_line"] # 获取需翻译行数
        line = data["line"] # 获取已翻译行数

        if total_line == line:
            return False
        else:
            return True

    # 翻译主流程
    def translation_start_target(self, continue_status: bool) -> None:
        # 设置内部状态（用于判断翻译任务是否实际在执行）
        self.translating = True

        # 设置翻译状态为正在翻译状态
        Base.work_status = Base.STATUS.TRANSLATING

        # 读取配置文件，并保存到该类中
        self.config.initialize()

        # 配置翻译平台信息
        self.config.prepare_for_translation()

        # 配置请求线程数
        self.config.thread_counts_setting()  # 需要在平台信息配置后面，依赖前面的数值 

        # 配置请求限制器
        self.request_limiter.set_limit(self.config.tpm_limit, self.config.rpm_limit)

        # 读取输入文件夹的文件，生成缓存
        self.print("")
        self.info(f"正在读取输入文件夹中的文件 ...")
        try:
            # 继续翻译时，直接读取缓存文件
            if continue_status == True: 
                self.cache_manager.load_from_file(self.config.label_output_path)
            
            # 初开始翻译
            else:
                # 读取输入文件夹的文件，生成缓存
                CacheProject = self.file_reader.read_files(
                        self.config.translation_project,
                        self.config.label_input_path,
                        self.config.label_input_exclude_rule
                    )
                # 读取完成后，保存到缓存管理器中
                self.cache_manager.load_from_project(CacheProject)

        except Exception as e:
            self.translating = False # 更改状态
            self.error("翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ... ", e)
            return None
        
        # 检查数据是否为空
        if self.cache_manager.get_item_count() == 0:
            self.translating = False # 更改状态
            self.error("翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ... ")
            return None

        # 输出每个文件的检测信息
        for _, file in self.cache_manager.project.files.items():
            # 获取信息
            language_stats = file.language_stats
            storage_path = file.storage_path
            encoding = file.encoding
            file_project_type = file.file_project_type

            # 输出信息
            self.print("")
            self.info(f"已经载入文件 - {storage_path}")
            self.info(f"文件类型 - {file_project_type}")
            self.info(f"文件编码 - {encoding}")
            self.info(f"语言统计 - {language_stats}")

        self.info(f"翻译项目数据全部载入成功 ...")
        self.print("")

        # 初开始翻译时，生成监控数据
        if continue_status == False:
            self.project_status_data = CacheProjectStatistics()
            self.cache_manager.project.stats_data = self.project_status_data
        # 继续翻译时加载存储的监控数据
        else:
            self.project_status_data = self.cache_manager.project.stats_data
            self.project_status_data.start_time = time.time() # 重置开始时间
            self.project_status_data.total_completion_tokens = 0 # 重置完成的token数量

        # 更新监控面板信息
        self.emit(Base.EVENT.TRANSLATION_UPDATE, self.project_status_data.to_dict())

        # 触发插件事件
        self.plugin_manager.broadcast_event("text_filter", self.config, self.cache_manager.project)
        self.plugin_manager.broadcast_event("preproces_text", self.config, self.cache_manager.project)

        # 根据最大轮次循环
        for current_round in range(self.config.round_limit + 1):
            # 检测是否需要停止任务
            if Base.work_status == Base.STATUS.STOPING:
                # 循环次数比实际最大轮次要多一轮，当触发停止翻译的事件时，最后都会从这里退出任务
                # 执行到这里说明停止任意的任务已经执行完毕，可以重置内部状态了
                self.translating = False
                return None

            # 获取 待翻译 状态的条目数量
            item_count_status_untranslated = self.cache_manager.get_item_count_by_status(TranslationStatus.UNTRANSLATED)

            # 判断是否需要继续翻译
            if item_count_status_untranslated == 0:
                self.print("")
                self.info("所有文本均已翻译，翻译任务已结束 ...")
                self.print("")
                break

            # 达到最大翻译轮次时
            if item_count_status_untranslated > 0 and current_round == self.config.round_limit:
                self.print("")
                self.warning("已达到最大翻译轮次，仍有部分文本未翻译，请检查结果 ...")
                self.print("")
                break

            # 第一轮时且不是继续翻译时，记录总行数
            if current_round == 0 and continue_status == False:
                self.project_status_data.total_line = item_count_status_untranslated

            # 第二轮开始对半切分
            if current_round > 0:
                self.config.lines_limit = max(1, int(self.config.lines_limit / 2))
                self.config.tokens_limit = max(1, int(self.config.tokens_limit / 2))

            # 生成缓存数据条目片段的合集列表，原文列表与上文列表一一对应
            chunks, previous_chunks, file_paths = self.cache_manager.generate_item_chunks(
                "line" if self.config.tokens_limit_switch == False else "token",
                self.config.lines_limit if self.config.tokens_limit_switch == False else self.config.tokens_limit,
                self.config.pre_line_counts
            )

            # 计算项目中出现次数最多的语言
            most_common_language = get_most_common_language(self.cache_manager.project)

            # 生成翻译任务合集列表
            tasks_list = []
            print("")
            self.info(f"正在生成翻译任务 ...")
            for chunk, previous_chunk, file_path in tqdm(zip(chunks, previous_chunks, file_paths),desc="生成翻译任务", total=len(chunks)):
                # 计算该任务所处文件的主要源语言
                new_source_lang = self.get_source_language_for_file(file_path)
                # 组装新源语言的对象
                source_lang = SourceLang(new=new_source_lang, most_common=most_common_language)

                task = TranslatorTask(self.config, self.plugin_manager, self.request_limiter, source_lang)  # 实例化
                task.set_items(chunk)  # 传入该任务待翻译原文
                task.set_previous_items(previous_chunk)  # 传入该任务待翻译原文的上文
                task.prepare(self.config.target_platform, self.config.prompt_preset)  # 预先构建消息列表
                tasks_list.append(task)
            self.info(f"已经生成全部翻译任务 ...")
            self.print("")

            # 输出开始翻译的日志
            self.print("")
            self.info(f"当前轮次 - {current_round + 1}")
            self.info(f"最大轮次 - {self.config.round_limit}")
            self.info(f"项目类型 - {self.config.translation_project}")
            self.info(f"原文语言 - {self.config.source_language}")
            self.info(f"译文语言 - {self.config.target_language}")
            self.print("")
            self.info(f"接口名称 - {self.config.platforms.get(self.config.target_platform, {}).get("name", "未知")}")
            self.info(f"接口地址 - {self.config.base_url}")
            self.info(f"模型名称 - {self.config.model}")
            self.print("")
            self.info(f"生效中的 网络代理 - {self.config.proxy_url}") if self.config.proxy_enable == True and self.config.proxy_url != "" else None
            self.info(f"生效中的 RPM 限额 - {self.config.rpm_limit}")
            self.info(f"生效中的 TPM 限额 - {self.config.tpm_limit}")

            # 根据提示词规则打印基础指令
            system = ""
            s_lang = self.config.source_language
            if self.config.prompt_preset == PromptBuilderEnum.CUSTOM:
                system = self.config.system_prompt_content
            elif self.config.target_platform == "LocalLLM":  # 需要放在前面，以免提示词预设的分支覆盖
                system = PromptBuilderLocal.build_system(self.config, s_lang)
            elif self.config.target_platform == "sakura":  # 需要放在前面，以免提示词预设的分支覆盖
                system = PromptBuilderSakura.build_system(self.config, s_lang)
            elif self.config.prompt_preset in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT):
                system = PromptBuilder.build_system(self.config, s_lang)
            elif self.config.prompt_preset == PromptBuilderEnum.THINK:
                system = PromptBuilderThink.build_system(self.config, s_lang)
            self.print("")
            if system:
                self.info(f"本次任务使用以下基础提示词：\n{system}\n") 

            self.info(f"即将开始执行翻译任务，预计任务总数为 {len(tasks_list)}, 同时执行的任务数量为 {self.config.actual_thread_counts}，请注意保持网络通畅 ...")
            time.sleep(3)
            self.print("")

            # 开始执行翻译任务,构建异步线程池
            with concurrent.futures.ThreadPoolExecutor(max_workers = self.config.actual_thread_counts, thread_name_prefix = "translator") as executor:
                for task in tasks_list:
                    future = executor.submit(task.start)
                    future.add_done_callback(self.task_done_callback)  # 为future对象添加一个回调函数，当任务完成时会被调用，更新数据

        # 等待可能存在的缓存文件写入请求处理完毕
        time.sleep(CacheManager.SAVE_INTERVAL)

        # 触发插件事件
        self.plugin_manager.broadcast_event("postprocess_text", self.config, self.cache_manager.project)

        # 如果开启了转换简繁开关功能，则进行文本转换
        if self.config.response_conversion_toggle:

            self.print("")
            self.info(f"已启动自动简繁转换功能，正在使用 {self.config.opencc_preset} 配置进行字形转换 ...")
            self.print("")

            converter = opencc.OpenCC(self.config.opencc_preset)
            cache_list = self.cache_manager.project.items_iter()
            for item in cache_list:
                if item.translation_status == TranslationStatus.TRANSLATED:
                    item.translated_text = converter.convert(item.translated_text)

        # 写入文件
        self.file_writer.output_translated_content(
            self.cache_manager.project,
            self.config.label_output_path,
            self.config.label_input_path,
        )
        self.print("")
        self.info(f"翻译结果已保存至 {self.config.label_output_path} 目录 ...")
        self.print("")

        # 重置内部状态（正常完成翻译）
        self.translating = False

        # 触发翻译停止完成的事件
        self.emit(Base.EVENT.TRANSLATION_STOP_DONE, {})
        self.plugin_manager.broadcast_event("translation_completed", self.config, self.cache_manager.project)


    # 单个翻译任务完成时,更新项目进度状态
    def task_done_callback(self, future: concurrent.futures.Future) -> None:
        try:
            # 获取结果
            result = future.result()

            # 结果为空则跳过后续的更新步骤
            if result == None or len(result) == 0:
                return

            # 更新翻译进度到缓存数据
            with self.project_status_data.atomic_scope():
                self.project_status_data.total_requests += 1
                self.project_status_data.error_requests += 0 if result.get("check_result") else 1
                self.project_status_data.line += result.get("row_count", 0)
                self.project_status_data.token += result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
                self.project_status_data.total_completion_tokens += result.get("completion_tokens", 0)
                self.project_status_data.time = time.time() - self.project_status_data.start_time
                stats_dict = self.project_status_data.to_dict()

            # 请求保存缓存文件
            self.cache_manager.require_save_to_file(self.config.label_output_path)

            # 触发翻译进度更新事件
            self.emit(Base.EVENT.TRANSLATION_UPDATE, stats_dict)
        except Exception as e:
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)

    def get_source_language_for_file(self, storage_path: str) -> str:
        """
        为文件确定适当的源语言
        Args:
            storage_path: 文件存储路径
        Returns:
            确定的源语言代码
        """
        # 获取配置文件中预置的源语言配置
        config_s_lang = self.config.source_language
        config_t_lang = self.config.target_language

        # 如果源语言配置不是自动配置，则直接返回源语言配置，否则使用下面获取到的lang_code
        if config_s_lang != 'auto':
            return config_s_lang

        # 获取文件的语言统计信息
        language_stats = self.cache_manager.project.get_file(storage_path).language_stats

        # 如果没有语言统计信息，返回'un'
        if not language_stats:
            return 'un'

        # 获取第一种语言
        first_source_lang = language_stats[0][0]

        # 将first_source_lang转换为与target_lang相同格式的语言名称，方便比较
        first_source_lang_name = TranslatorUtil.map_language_code_to_name(first_source_lang)

        # 检查第一语言是否与目标语言一致
        if first_source_lang_name == config_t_lang:
            # 如果一致，尝试使用第二种语言
            if len(language_stats) > 1:
                return language_stats[1][0]  # 返回第二种语言
            else:
                # 没有第二种语言，返回'un'
                return 'un'
        else:
            # 如果不一致，直接使用第一种语言
            return first_source_lang
