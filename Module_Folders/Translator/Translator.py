import time
import threading
import concurrent.futures

import opencc
from tqdm import tqdm

from Base.Base import Base
from Base.PluginManager import PluginManager
from Module_Folders.PromptBuilder import PromptBuilder
from Module_Folders.Cache.CacheItem import CacheItem
from Module_Folders.Cache.CacheManager import CacheManager
from Module_Folders.Translator.TranslatorTask import TranslatorTask
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig
from Module_Folders.File_Reader.File1 import File_Reader
from Module_Folders.File_Outputer.File2 import File_Outputter
from Module_Folders.Request_Limiter.Request_limit import Request_Limiter

# 翻译器
class Translator(Base):

    def __init__(self, plugin_manager: PluginManager) -> None:
        super().__init__()

        # 初始化
        self.plugin_manager = plugin_manager
        self.config = TranslatorConfig()
        self.cache_manager = CacheManager()
        self.request_limiter = Request_Limiter()

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
        File_Outputter.output_translated_content(
            self,
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

    # 实际的翻译流程
    def translation_start_target(self, continue_status: bool) -> None:
        # 设置内部状态（用于判断翻译任务是否实际在执行）
        self.translating = True

        # 设置翻译状态为正在翻译状态
        Base.work_status = Base.STATUS.TRANSLATING

        # 初始化
        self.config.initialize()

        # 请求线程数
        self.config.request_thread_counts()

        # 生成缓存列表
        try:
            if continue_status == True:
                self.cache_manager.load_from_file(self.config.label_output_path)
            else:
                self.cache_manager.load_from_list(
                    File_Reader.read_files(
                        self,
                        self.config.translation_project,
                        self.config.label_input_path,
                    )
                )

            # 检查数据是否为空
            if self.cache_manager.get_item_count() == 0:
                raise Exception("self.cache_manager.get_item_count() == 0")
        except Exception as e:
            self.error("翻译项目数据载入失败 ... ", e)
            return None

        # 从头翻译时加载默认数据
        if continue_status == False:
            self.data = {
                "start_time": time.time(),
                "total_line": 0,
                "line": 0,
                "token": 0,
                "total_completion_tokens": 0,
                "time": 0,
            }
        else:
            self.data = self.cache_manager.get_project_data()
            self.data["start_time"] = time.time() - self.data.get("time", 0)

        # 更新翻译进度
        self.emit(Base.EVENT.TRANSLATION_UPDATE, self.data)

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

            # 生成混合翻译参数
            split, model = True, None
            if self.config.mix_translation_enable == True:
                split, model, self.config.target_platform = self.generate_mix_translation_params(current_round)

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
                self.data["total_line"] = item_count_status_untranslated

            # 第二轮开始对半切分
            if current_round > 0 and split == True:
                self.config.lines_limit = max(1, int(self.config.lines_limit / 2))
                self.config.tokens_limit = max(1, int(self.config.tokens_limit / 2))

            # 配置翻译平台信息
            self.config.prepare_for_translation(model)

            # 配置请求限制器，依赖前面的配置信息
            self.request_limiter.set_limit(self.config.max_tokens, self.config.tpm_limit, self.config.rpm_limit)

            # 生成缓存数据条目片段
            t = time.time()
            chunks, previous_chunks = self.cache_manager.generate_item_chunks(
                "line" if self.config.tokens_limit_switch == False else "token",
                self.config.lines_limit if self.config.tokens_limit_switch == False else self.config.tokens_limit,
                self.config.pre_line_counts
            )

            # 生成翻译任务
            tasks = []
            self.print("")
            for chunk, previous_chunk in tqdm(zip(chunks, previous_chunks), desc = "生成翻译任务", total = len(chunks)):
                task = TranslatorTask(self.config, self.plugin_manager, self.request_limiter)
                task.set_items(chunk)
                task.set_previous_items(previous_chunk)
                task.prepare(
                    self.config.target_platform,
                    self.config.platforms.get(self.config.target_platform).get("api_format")
                )
                tasks.append(task)
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
            self.info(f"生效中的 MAX_TOKENS 限额 - {self.config.max_tokens}")
            self.print("")
            self.info(f"本次任务使用以下基础指令：\n{PromptBuilder.get_system_prompt(self.config)}\n") if self.config.target_platform != "sakura" else None
            self.info(f"即将开始执行翻译任务，预计任务总数为 {len(tasks)}, 同时执行的任务数量为 {self.config.actual_thread_counts}，请注意保持网络通畅 ...")
            self.print("")

            # 开始执行翻译任务
            with concurrent.futures.ThreadPoolExecutor(max_workers = self.config.actual_thread_counts, thread_name_prefix = "translator") as executor:
                for task in tasks:
                    future = executor.submit(task.start)
                    future.add_done_callback(self.task_done_callback)

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
        File_Outputter.output_translated_content(
            self,
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
        self.plugin_manager.broadcast_event("translation_completed", self.config, None)

    # 生成混合翻译参数
    def generate_mix_translation_params(self, current_round: int) -> tuple[bool, str, str]:
        split = True
        model = None

        if current_round == 0:
            target_platform = self.config.mix_translation_settings.get("translation_platform_1")
        elif current_round == 1:
            split = self.config.mix_translation_settings.get("split_switch_2")
            target_platform = self.config.mix_translation_settings.get("translation_platform_2")
            if self.config.mix_translation_settings.get("model_type_2") != "":
                model = self.config.mix_translation_settings.get("model_type_2")
        elif current_round >= 2:
            split = self.config.mix_translation_settings.get("split_switch_3")
            target_platform = self.config.mix_translation_settings.get("translation_platform_3")
            if self.config.mix_translation_settings.get("model_type_3") != "":
                model = self.config.mix_translation_settings.get("model_type_3")

        return split, model, target_platform

    # 执行简繁转换
    def convert_simplified_and_traditional(self, preset: str, cache_list: list[dict]) -> list[dict]:
        converter = opencc.OpenCC(preset)

        for item in [item for item in cache_list if item.get("translation_status") == CacheItem.STATUS.TRANSLATED]:
            item["translated_text"] = converter.convert(item.get("translated_text"))

        return cache_list

    # 翻译任务完成时
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
                    new["start_time"] = self.data.get("start_time")
                    new["total_line"] = self.data.get("total_line")
                    new["line"] = self.data.get("line") + result.get("row_count", 0)
                    new["token"] = self.data.get("token") + result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
                    new["total_completion_tokens"] = self.data.get("total_completion_tokens") + result.get("completion_tokens")
                    new["time"] = time.time() - self.data.get("start_time")
                    self.data = new
                else:
                    new = {}
                    new["start_time"] = self.data.get("start_time")
                    new["total_line"] = self.data.get("total_line")
                    new["line"] = self.data.get("line")
                    new["token"] = self.data.get("token") + result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
                    new["total_completion_tokens"] = self.data.get("total_completion_tokens")
                    new["time"] = time.time() - self.data.get("start_time")
                    self.data = new

            # 更新翻译进度到缓存数据
            self.cache_manager.set_project_data(self.data)

            # 请求保存缓存文件
            self.cache_manager.require_save_to_file(self.config.label_output_path)

            # 触发翻译进度更新事件
            self.emit(Base.EVENT.TRANSLATION_UPDATE, self.data)
        except Exception as e:
            if self.is_debug():
                self.error("翻译任务错误 ...", e)
            else:
                self.error(f"翻译任务错误 ... {e}", None)