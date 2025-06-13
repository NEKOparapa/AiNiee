import time
import threading
import concurrent.futures
from dataclasses import dataclass

import opencc
from tqdm import tqdm

from Base.Base import Base
from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.Cache.CacheManager import CacheManager
from ModuleFolders.Cache.CacheProject import CacheProjectStatistics
from ModuleFolders.TaskExecutor import TranslatorUtil
from ModuleFolders.TaskExecutor.TaskType import TaskType
from ModuleFolders.TaskExecutor.TranslatorTask import TranslatorTask
from ModuleFolders.TaskExecutor.PolisherTask import PolisherTask
from ModuleFolders.TaskExecutor.TaskConfig import TaskConfig
from ModuleFolders.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.PromptBuilder.PromptBuilderPolishing import PromptBuilderPolishing
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal
from ModuleFolders.PromptBuilder.PromptBuilderSakura import PromptBuilderSakura
from ModuleFolders.RequestLimiter.RequestLimiter import RequestLimiter
from ModuleFolders.TaskExecutor.TranslatorUtil import get_most_common_language


@dataclass
class SourceLang:
    new: str
    most_common: str


# 翻译器
class TaskExecutor(Base):

    def __init__(self, plugin_manager,cache_manager, file_reader, file_writer) -> None:
        super().__init__()

        # 初始化
        self.plugin_manager = plugin_manager
        self.cache_manager = cache_manager
        self.file_reader = file_reader
        self.file_writer = file_writer
        self.config = TaskConfig()
        self.request_limiter = RequestLimiter()

        # 注册事件
        self.subscribe(Base.EVENT.TASK_STOP, self.task_stop)
        self.subscribe(Base.EVENT.TASK_START, self.task_start)
        self.subscribe(Base.EVENT.TASK_MANUAL_EXPORT, self.task_manual_export)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.app_shut_down)

    # 应用关闭事件
    def app_shut_down(self, event: int, data: dict) -> None:
        Base.work_status = Base.STATUS.STOPING

    # 手动导出事件
    def task_manual_export(self, event: int, data: dict) -> None:
        # 确保当前状态为 翻译中
        if Base.work_status != Base.STATUS.TRANSLATING:
            return None

        # 触发手动导出插件事件
        self.plugin_manager.broadcast_event("manual_export", self.config, self.cache_manager.project)

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

            self.print("")
            self.info(f"已启动自动简繁转换功能，正在使用 {self.config.opencc_preset} 配置进行字形转换 ...")
            self.print("")

        # 写入文件
        self.file_writer.output_translated_content(
            self.cache_manager.project,
            self.config.label_output_path,
            self.config.label_input_path,
        )

    # 任务停止事件
    def task_stop(self, event: int, data: dict) -> None:
        # 设置运行状态为停止中
        Base.work_status = Base.STATUS.STOPING

        def target() -> None:
            while True:
                time.sleep(0.5)
                if self.translating == False:
                    self.print("")
                    self.info("翻译任务已停止 ...")
                    self.print("")
                    self.emit(Base.EVENT.TASK_STOP_DONE, {})
                    break

        threading.Thread(target = target).start()

    # 任务开始事件
    def task_start(self, event: int, data: dict) -> None:
        # 获取配置信息
        continue_status = data.get("continue_status")
        current_mode = data.get("current_mode")

        # 翻译任务
        if current_mode == TaskType.TRANSLATION:
            threading.Thread(
                target = self.translation_start_target,
                args = (continue_status,),
            ).start()
        
        # 润色任务
        elif current_mode == TaskType.POLISH:
            threading.Thread(
                target = self.polish_start_target,
                args = (continue_status,),
            ).start()

        else:
            self.print("")
            self.error(f"非法的翻译模式：{current_mode}，请检查配置文件 ...")
            self.print("")
            return None

    # 翻译主流程
    def translation_start_target(self, continue_status: bool) -> None:
        # 设置内部状态（用于判断翻译任务是否实际在执行）
        self.translating = True

        # 设置翻译状态为正在翻译状态
        Base.work_status = Base.STATUS.TRANSLATING

        # 读取配置文件，并保存到该类中
        self.config.initialize()

        # 配置翻译平台信息
        self.config.prepare_for_translation(TaskType.TRANSLATION)

        # 配置请求限制器
        self.request_limiter.set_limit(self.config.tpm_limit, self.config.rpm_limit)

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
        self.emit(Base.EVENT.TASK_UPDATE, self.project_status_data.to_dict())

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
                self.config.pre_line_counts,
                TaskType.TRANSLATION
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
                task.prepare(self.config.target_platform)  # 预先构建消息列表
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
            self.info(f"RPM 限额 - {self.config.rpm_limit}")
            self.info(f"TPM 限额 - {self.config.tpm_limit}")

            # 根据提示词规则打印基础指令
            system = ""
            s_lang = self.config.source_language
            if self.config.target_platform == "LocalLLM":  # 需要放在前面，以免提示词预设的分支覆盖
                system = PromptBuilderLocal.build_system(self.config, s_lang)
            elif self.config.target_platform == "sakura":  # 需要放在前面，以免提示词预设的分支覆盖
                system = PromptBuilderSakura.build_system(self.config, s_lang)
            elif self.config.translation_prompt_selection["last_selected_id"] in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT, PromptBuilderEnum.THINK):
                system = PromptBuilder.build_system(self.config, s_lang)
            else:
                system = self.config.translation_prompt_selection["prompt_content"]
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
        self.emit(Base.EVENT.TASK_STOP_DONE, {})
        self.plugin_manager.broadcast_event("translation_completed", self.config, self.cache_manager.project)

        # 触发翻译完成事件
        self.emit(Base.EVENT.TASK_COMPLETED, {})

    # 润色主流程
    def polish_start_target(self, continue_status: bool) -> None:
        # 设置内部状态（用于判断翻译任务是否实际在执行）
        self.translating = True

        # 设置翻译状态为正在翻译状态
        Base.work_status = Base.STATUS.TRANSLATING

        # 读取配置文件，并保存到该类中
        self.config.initialize()

        # 配置翻译平台信息
        self.config.prepare_for_translation(TaskType.POLISH)

        # 配置请求限制器
        self.request_limiter.set_limit(self.config.tpm_limit, self.config.rpm_limit)

        # 初开始任务时，生成监控数据
        if continue_status == False:
            self.project_status_data = CacheProjectStatistics()
            self.cache_manager.project.stats_data = self.project_status_data
        # 继续翻译时加载存储的监控数据
        else:
            self.project_status_data = self.cache_manager.project.stats_data
            self.project_status_data.start_time = time.time() # 重置开始时间
            self.project_status_data.total_completion_tokens = 0 # 重置完成的token数量

        # 更新监控面板信息
        self.emit(Base.EVENT.TASK_UPDATE, self.project_status_data.to_dict())

        # 触发插件事件
        self.plugin_manager.broadcast_event("text_filter", self.config, self.cache_manager.project)


        # 根据最大轮次循环
        for current_round in range(self.config.round_limit + 1):
            # 检测是否需要停止任务
            if Base.work_status == Base.STATUS.STOPING:
                # 循环次数比实际最大轮次要多一轮，当触发停止翻译的事件时，最后都会从这里退出任务
                # 执行到这里说明停止任意的任务已经执行完毕，可以重置内部状态了
                self.translating = False
                return None

            # 根据润色模式，获取可润色的条目数量
            if self.config.polishing_mode_selection == "source_text_polish":
                item_count_status_unpolishd = self.cache_manager.get_item_count_by_status(TranslationStatus.UNTRANSLATED)
            elif self.config.polishing_mode_selection == "translated_text_polish":
                item_count_status_unpolishd = self.cache_manager.get_item_count_by_status(TranslationStatus.TRANSLATED)

            # 判断是否需要继续润色
            if item_count_status_unpolishd == 0:
                self.print("")
                self.info("所有文本均已润色，润色任务已结束 ...")
                self.print("")
                break

            # 达到最大任务轮次时
            if item_count_status_unpolishd > 0 and current_round == self.config.round_limit:
                self.print("")
                self.warning("已达到最大任务轮次，仍有部分文本未翻译，请检查结果 ...")
                self.print("")
                break

            # 第一轮时且不是继续翻译时，记录总行数
            if current_round == 0 and continue_status == False:
                self.project_status_data.total_line = item_count_status_unpolishd

            # 第二轮开始对半切分
            if current_round > 0:
                self.config.lines_limit = max(1, int(self.config.lines_limit / 2))
                self.config.tokens_limit = max(1, int(self.config.tokens_limit / 2))

            # 生成缓存数据条目片段的合集列表
            if self.config.polishing_mode_selection == "source_text_polish":
                chunks, previous_chunks, file_paths = self.cache_manager.generate_item_chunks(
                    "line" if self.config.tokens_limit_switch == False else "token",
                    self.config.lines_limit if self.config.tokens_limit_switch == False else self.config.tokens_limit,
                    self.config.polishing_pre_line_counts,
                    TaskType.TRANSLATION
                )
            elif self.config.polishing_mode_selection == "translated_text_polish":
                chunks, previous_chunks, file_paths = self.cache_manager.generate_item_chunks(
                    "line" if self.config.tokens_limit_switch == False else "token",
                    self.config.lines_limit if self.config.tokens_limit_switch == False else self.config.tokens_limit,
                    self.config.polishing_pre_line_counts,
                    TaskType.POLISH
                )

            # 计算项目中出现次数最多的语言
            most_common_language = get_most_common_language(self.cache_manager.project)

            # 生成润色任务合集列表
            tasks_list = []
            print("")
            self.info(f"正在生成润色任务 ...")
            for chunk, previous_chunk, file_path in tqdm(zip(chunks, previous_chunks, file_paths),desc="生成润色任务", total=len(chunks)):
                task = PolisherTask(self.config, self.plugin_manager, self.request_limiter)  # 实例化
                task.set_items(chunk)  # 传入该任务待润色文
                task.set_previous_items(previous_chunk)  # 传入该任务待润色文的上文
                task.prepare()  # 预先构建消息列表
                tasks_list.append(task)
            self.info(f"已经生成全部润色任务 ...")
            self.print("")

            # 输出开始翻译的日志
            self.print("")
            self.info(f"当前轮次 - {current_round + 1}")
            self.info(f"最大轮次 - {self.config.round_limit}")
            self.info(f"项目类型 - {self.config.translation_project}")
            self.print("")
            self.info(f"接口名称 - {self.config.platforms.get(self.config.target_platform, {}).get("name", "未知")}")
            self.info(f"接口地址 - {self.config.base_url}")
            self.info(f"模型名称 - {self.config.model}")
            self.print("")
            self.info(f"RPM 限额 - {self.config.rpm_limit}")
            self.info(f"TPM 限额 - {self.config.tpm_limit}")

            # 根据提示词规则打印基础指令
            system = ""
            if self.config.polishing_prompt_selection["last_selected_id"] == PromptBuilderEnum.REFINEMENT_COMMON:
                system = PromptBuilderPolishing.build_system(self.config)
            else:
                system = self.config.polishing_prompt_selection["prompt_content"]
            self.print("")
            if system:
                self.info(f"本次任务使用以下基础提示词：\n{system}\n") 

            self.info(f"即将开始执行润色任务，预计任务总数为 {len(tasks_list)}, 同时执行的任务数量为 {self.config.actual_thread_counts}，请注意保持网络通畅 ...")
            time.sleep(3)
            self.print("")

            # 开始执行润色务,构建异步线程池
            with concurrent.futures.ThreadPoolExecutor(max_workers = self.config.actual_thread_counts, thread_name_prefix = "translator") as executor:
                for task in tasks_list:
                    future = executor.submit(task.start)
                    future.add_done_callback(self.task_done_callback)  # 为future对象添加一个回调函数，当任务完成时会被调用，更新数据

        # 等待可能存在的缓存文件写入请求处理完毕
        time.sleep(CacheManager.SAVE_INTERVAL)

        # 写入文件
        self.file_writer.output_translated_content(
            self.cache_manager.project,
            self.config.polishing_output_path,
            self.config.label_input_path,
        )
        self.print("")
        self.info(f"润色结果已保存至 {self.config.polishing_output_path} 目录 ...")
        self.print("")

        # 重置内部状态
        self.translating = False

        # 触发事件
        self.emit(Base.EVENT.TASK_STOP_DONE, {})     # 翻译停止完成的事件
        self.emit(Base.EVENT.TASK_COMPLETED, {})     # 翻译完成事件



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
            self.emit(Base.EVENT.TASK_UPDATE, stats_dict)
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
