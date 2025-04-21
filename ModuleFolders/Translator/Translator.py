import os
import time
import threading
import concurrent.futures

import opencc
from tqdm import tqdm

from Base.Base import Base
from Base.PluginManager import PluginManager
from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheManager import CacheManager
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

        # 线程锁
        self.data_lock = threading.Lock()

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
        # 先转换为列表，再交给插件进行处理（兼容旧版接口）
        cache_list = self.cache_manager.to_list()
        self.plugin_manager.broadcast_event("manual_export", self.config, cache_list)

        # 如果开启了转换简繁开关功能，则进行文本转换
        if self.config.response_conversion_toggle:
            cache_list = self.convert_simplified_and_traditional(self.config.opencc_preset, cache_list)
            self.print("")
            self.info(f"已启动自动简繁转换功能，正在使用 {self.config.opencc_preset} 配置进行字形转换 ...")
            self.print("")

        # 写入文件
        self.file_writer.output_translated_content(
            cache_list,
            self.config.label_output_path,
            self.config.label_input_path,
        )

    # 翻译状态检查事件
    def translation_continue_check(self, event: int, data: dict) -> None:
        threading.Thread(
            target = self.translation_continue_check_target
        ).start()

    # 翻译状态检查
    def translation_continue_check_target(self) -> None:
        # 等一下，等页面切换效果结束再执行，避免争抢 CPU 资源，导致 UI 卡顿
        time.sleep(0.5)

        # 检查结果的默认值
        continue_status = False

        # 只有翻译状态为 无任务 时才执行检查逻辑，其他情况直接返回默认值
        if Base.work_status == Base.STATUS.IDLE:
            config = self.load_config()
            self.cache_manager.load_from_file(config.get("label_output_path", ""))
            continue_status = self.cache_manager.get_continue_status()

        self.emit(Base.EVENT.TRANSLATION_CONTINUE_CHECK_DONE, {
            "continue_status" : continue_status,
        })

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

        # 如果开启自动设置输出文件夹功能，设置为输入文件夹的平级目录
        if self.config.auto_set_output_path == True:
            abs_input_path = os.path.abspath(self.config.label_input_path)
            parent_dir = os.path.dirname(abs_input_path)
            output_folder_name = "AiNieeOutput"
            self.config.label_output_path = os.path.join(parent_dir, output_folder_name)

           # 保存新配置
            config = self.load_config()
            config["label_output_path"] = self.config.label_output_path
            self.save_config(config)


        # 读取输入文件夹的文件，生成缓存
        try:
            if continue_status == True:
                self.cache_manager.load_from_file(self.config.label_output_path)
            else:
                self.cache_manager.load_from_tuple(
                    self.file_reader.read_files(
                        self.config.translation_project,
                        self.config.label_input_path,
                        self.config.label_input_exclude_rule
                    )
                )
        except Exception as e:
            self.translating = False # 更改状态
            self.error("翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ... ", e)
            return None
        
        
        # 检查数据是否为空
        if self.cache_manager.get_item_count() == 0:
            self.translating = False # 更改状态
            self.error("翻译项目数据载入失败 ... 请检查是否正确设置项目类型与输入文件夹 ... ")
            return None


        # 从头翻译时加载默认数据
        if continue_status == False:
            self.project_status_data = {
                "total_requests": 0,
                "error_requests": 0,
                "start_time": time.time(),
                "total_line": 0,
                "line": 0,
                "token": 0,
                "total_completion_tokens": 0,
                "time": 0,
            }
        else:
            self.project_status_data = self.cache_manager.get_project_data()
            self.project_status_data["start_time"] = time.time() - self.project_status_data.get("time", 0)

        # 更新翻译进度
        self.emit(Base.EVENT.TRANSLATION_UPDATE, self.project_status_data)

        # 触发插件事件
        # 先转换为列表，在事件结束后再转换回来（兼容旧版接口）
        cache_list = self.cache_manager.to_list()
        self.plugin_manager.broadcast_event("text_filter", self.config, cache_list)
        self.plugin_manager.broadcast_event("preproces_text", self.config, cache_list)
        self.cache_manager.load_from_list(cache_list)

        # 开始循环
        for current_round in range(self.config.round_limit + 1):
            # 检测是否需要停止任务
            if Base.work_status == Base.STATUS.STOPING:
                # 循环次数比实际最大轮次要多一轮，当触发停止翻译的事件时，最后都会从这里退出任务
                # 执行到这里说明停止任意的任务已经执行完毕，可以重置内部状态了
                self.translating = False
                return None

            # 获取 待翻译 状态的条目数量
            item_count_status_untranslated = self.cache_manager.get_item_count_by_status(CacheItem.STATUS.UNTRANSLATED)

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
                self.project_status_data["total_line"] = item_count_status_untranslated

            # 第二轮开始对半切分
            if current_round > 0:
                self.config.lines_limit = max(1, int(self.config.lines_limit / 2))
                self.config.tokens_limit = max(1, int(self.config.tokens_limit / 2))


            # 生成缓存数据条目片段的合集列表，原文列表与上文列表一一对应
            chunks, previous_chunks = self.cache_manager.generate_item_chunks(
                "line" if self.config.tokens_limit_switch == False else "token",
                self.config.lines_limit if self.config.tokens_limit_switch == False else self.config.tokens_limit,
                self.config.pre_line_counts
            )

            # 生成翻译单元任务的合集列表
            tasks_list = []
            self.print("")
            for chunk, previous_chunk in tqdm(zip(chunks, previous_chunks), desc = "生成翻译任务", total = len(chunks)):
                task = TranslatorTask(self.config, self.plugin_manager, self.request_limiter) # 实例化
                task.set_items(chunk)  #传入该任务待翻译原文
                task.set_previous_items(previous_chunk) # 传入该任务待翻译原文的上文
                task.prepare(self.config.target_platform,self.config.prompt_preset) # 预先构建消息列表
                tasks_list.append(task)
            self.print("")

            # 输出开始翻译的日志
            self.print("")
            self.info(f"当前轮次 - {current_round + 1}")
            self.info(f"最大轮次 - {self.config.round_limit}")
            self.info(f"项目类型 - {self.config.translation_project}")
            self.info(f"原文语言 - {self.config.source_language}")
            self.info(f"译文语言 - {self.config.target_language}")
            self.print("")
            if self.config.double_request_switch_settings == False:
                self.info(f"接口名称 - {self.config.platforms.get(self.config.target_platform, {}).get("name", "未知")}")
                self.info(f"接口地址 - {self.config.base_url}")
                self.info(f"模型名称 - {self.config.model}")
                self.print("")
                self.info(f"生效中的 网络代理 - {self.config.proxy_url}") if self.config.proxy_enable == True and self.config.proxy_url != "" else None
                self.info(f"生效中的 RPM 限额 - {self.config.rpm_limit}")
                self.info(f"生效中的 TPM 限额 - {self.config.tpm_limit}")

                # 根据提示词规则打印基础指令
                system = ""
                if self.config.prompt_preset == PromptBuilderEnum.CUSTOM:
                    system = self.config.system_prompt_content
                elif self.config.target_platform == "LocalLLM": # 需要放在前面，以免提示词预设的分支覆盖
                    system = PromptBuilderLocal.build_system(self.config)
                elif self.config.target_platform == "sakura": # 需要放在前面，以免提示词预设的分支覆盖
                    system = PromptBuilderSakura.build_system(self.config)
                elif self.config.prompt_preset in (PromptBuilderEnum.COMMON, PromptBuilderEnum.COT):
                    system = PromptBuilder.build_system(self.config)
                elif self.config.prompt_preset == PromptBuilderEnum.THINK:
                    system = PromptBuilderThink.build_system(self.config)
                self.print("")
                if system:
                    self.info(f"本次任务使用以下基础提示词：\n{system}\n") 
                    
            else:
                self.info(f"第一次请求的接口 - {self.config.platforms.get(self.config.request_a_platform_settings, {}).get("name", "未知")}")
                self.info(f"接口地址 - {self.config.base_url_a}")
                self.info(f"模型名称 - {self.config.model_a}")
                self.print("")

                self.info(f"第二次请求的接口 - {self.config.platforms.get(self.config.request_b_platform_settings, {}).get("name", "未知")}")
                self.info(f"接口地址 - {self.config.base_url_b}")
                self.info(f"模型名称 - {self.config.model_b}")
                self.print("")

                self.info(f"生效中的 网络代理 - {self.config.proxy_url}") if self.config.proxy_enable == True and self.config.proxy_url != "" else None
                self.info(f"生效中的 RPM 限额 - {self.config.rpm_limit}")
                self.info(f"生效中的 TPM 限额 - {self.config.tpm_limit}")
                self.print("")

            self.info(f"即将开始执行翻译任务，预计任务总数为 {len(tasks_list)}, 同时执行的任务数量为 {self.config.actual_thread_counts}，请注意保持网络通畅 ...")
            self.print("")

            # 开始执行翻译任务,构建异步线程池
            with concurrent.futures.ThreadPoolExecutor(max_workers = self.config.actual_thread_counts, thread_name_prefix = "translator") as executor:
                for task in tasks_list:
                    future = executor.submit(task.start)
                    future.add_done_callback(self.task_done_callback) # 为future对象添加一个回调函数，当任务完成时会被调用，更新数据




        # 等待可能存在的缓存文件写入请求处理完毕
        time.sleep(CacheManager.SAVE_INTERVAL)

        # 触发插件事件
        # 先转换为列表，再交给插件进行处理（兼容旧版接口）
        cache_list = self.cache_manager.to_list()
        self.plugin_manager.broadcast_event("postprocess_text", self.config, cache_list)

        # 如果开启了转换简繁开关功能，则进行文本转换
        if self.config.response_conversion_toggle:
            cache_list = self.convert_simplified_and_traditional(self.config.opencc_preset, cache_list)
            self.print("")
            self.info(f"已启动自动简繁转换功能，正在使用 {self.config.opencc_preset} 配置进行字形转换 ...")
            self.print("")

        # 写入文件
        self.file_writer.output_translated_content(
            cache_list,
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
        self.plugin_manager.broadcast_event("translation_completed", self.config, cache_list)

    # 执行简繁转换
    def convert_simplified_and_traditional(self, preset: str, cache_list: list[dict]) -> list[dict]:
        converter = opencc.OpenCC(preset)

        for item in [item for item in cache_list if item.get("translation_status") == CacheItem.STATUS.TRANSLATED]:
            item["translated_text"] = converter.convert(item.get("translated_text"))

        return cache_list

    # 单个翻译任务完成时,更新项目进度状态
    def task_done_callback(self, future: concurrent.futures.Future) -> None:
        try:
            # 获取结果
            result = future.result()

            # 结果为空则跳过后续的更新步骤
            if result == None or len(result) == 0:
                return

            # 记录数据
            with self.data_lock:
                if result.get("check_result") == True:
                    new = {}
                    new["total_requests"] = self.project_status_data.get("total_requests") + 1
                    new["error_requests"] = self.project_status_data.get("error_requests")
                    new["start_time"] = self.project_status_data.get("start_time")
                    new["total_line"] = self.project_status_data.get("total_line")
                    new["line"] = self.project_status_data.get("line") + result.get("row_count", 0)
                    new["token"] = self.project_status_data.get("token") + result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
                    new["total_completion_tokens"] = self.project_status_data.get("total_completion_tokens") + result.get("completion_tokens")
                    new["time"] = time.time() - self.project_status_data.get("start_time")
                    self.project_status_data = new
                else:
                    new = {}
                    new["total_requests"] = self.project_status_data.get("total_requests") + 1
                    new["error_requests"] = self.project_status_data.get("error_requests") + 1
                    new["start_time"] = self.project_status_data.get("start_time")
                    new["total_line"] = self.project_status_data.get("total_line")
                    new["line"] = self.project_status_data.get("line")
                    new["token"] = self.project_status_data.get("token") + result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
                    new["total_completion_tokens"] = self.project_status_data.get("total_completion_tokens")
                    new["time"] = time.time() - self.project_status_data.get("start_time")
                    self.project_status_data = new

            # 更新翻译进度到缓存数据
            self.cache_manager.set_project_data(self.project_status_data)

            # 请求保存缓存文件
            self.cache_manager.require_save_to_file(self.config.label_output_path)

            # 触发翻译进度更新事件
            self.emit(Base.EVENT.TRANSLATION_UPDATE, self.project_status_data)
        except Exception as e:
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)