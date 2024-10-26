import os
import copy
import time
import json
import threading
import concurrent.futures

from Base.AiNieeBase import AiNieeBase
from Module_Folders.File_Reader.File1 import File_Reader
from Module_Folders.Cache_Manager.Cache import Cache_Manager
from Module_Folders.File_Outputer.File2 import File_Outputter
from Module_Folders.Request_Limiter.Request_limit import Request_Limiter
from Module_Folders.TranslatorTask import TranslatorTask

# 翻译器
class Translator(AiNieeBase):

    # 缓存文件保存周期（毫秒）
    CACHE_FILE_SAVE_INTERVAL = 3000

    def __init__(self, configurator, plugin_manager):
        super().__init__()

        # 初始化
        self.configurator = configurator
        self.plugin_manager = plugin_manager
        self.request_limiter = Request_Limiter(configurator)

        # 线程锁
        self.lock = threading.Lock()
        self.cache_data_lock = threading.Lock()
        self.cache_file_lock = threading.Lock()

        # 注册事件
        self.subscribe(self.EVENT.TRANSLATION_STOP, self.translation_stop)
        self.subscribe(self.EVENT.TRANSLATION_START, self.translation_start)
        self.subscribe(self.EVENT.TRANSLATION_CONTINUE_CHECK, self.translation_continue_check)

        # 定时器
        threading.Thread(target = self.save_cache_file_tick).start()

    # 翻译停止事件
    def translation_stop(self, event: int, data: dict):
        # 设置运行状态为停止中
        self.configurator.Running_status = self.STATUS.STOPING

        def target():
            while True:
                time.sleep(0.5)
                if len([t for t in threading.enumerate() if "translator" in t.name]) == 0:
                    self.configurator.Running_status = self.STATUS.IDLE
                    self.emit(self.EVENT.TRANSLATION_STOP_DONE, {})
                    break

        threading.Thread(target = target).start()

    # 翻译开始事件
    def translation_start(self, event: int, data: dict):
        threading.Thread(
            target = self.translation_start_target,
            args = (data.get("translation_continue"),),
        ).start()

    # 翻译状态检查事件
    def translation_continue_check(self, event: int, data: dict):
        translation_continue = False
        try:
            cache = self.load_cache_file(f"{self.configurator.label_output_path}/cache/AinieeCacheData.json")
            untranslated_text_line_count, _ = Cache_Manager.count_and_update_translation_status_0_2(
                self,
                cache,
            )
            translation_continue = untranslated_text_line_count > 0
        except Exception:
            self.error("缓存文件读取失败 ...", e)
        finally:
            self.emit(self.EVENT.TRANSLATION_CONTINUE_CHECK_DONE, {
                "translation_continue" : translation_continue,
            })

    # 实际的翻译流程
    def translation_start_target(self, translation_continue):
        # 设置翻译状态为正在翻译状态
        self.configurator.Running_status = self.STATUS.TRANSLATION

        # 读取配置文件
        self.configurator.load_config_file()

        # 根据是否继续翻译载入项目数据
        default_data = {
            "status": "翻译中",
            "start_time": time.time(),
            "total_line": 0,
            "line": 0,
            "remaining_line": 0,
            "token": 0,
            "total_completion_tokens": 0,
            "time": 0,
            "remaining_time": 0,
            "speed": 0,
            "task": 0,
        }

        if translation_continue:
            # 读取文本
            try:
                self.configurator.cache_list = self.load_cache_file(f"{self.configurator.label_output_path}/cache/AinieeCacheData.json")
            except Exception as e:
                self.error("翻译项目数据载入失败 ... ", e)
                return {}

            # 初始化数据
            if len(self.configurator.cache_list) == 0:
                self.data = default_data
            else:
                self.data = self.configurator.cache_list[0].get("data", {})
                self.data["status"] = "翻译中"
                self.data["start_time"] = time.time() - self.data.get("time", 0)
        else:
            # 读取文本
            try:
                self.configurator.cache_list = File_Reader.read_files(
                    self,
                    self.configurator.translation_project,
                    self.configurator.label_input_path,
                )
            except Exception as e:
                self.error("翻译项目数据载入失败 ... ", e)
                return {}

            # 初始化数据
            self.data = default_data

        # 更新翻译进度
        self.emit(self.EVENT.TRANSLATION_UPDATE, self.data)

        # 调用插件，进行文本过滤
        self.plugin_manager.broadcast_event(
            "text_filter",
            self.configurator,
            self.configurator.cache_list,
        )

        # 调用插件，进行文本预处理
        self.plugin_manager.broadcast_event(
            "preproces_text",
            self.configurator,
            self.configurator.cache_list,
        )

        # 配置请求限制器，依赖前面的配置信息
        self.request_limiter.set_limit(
            self.configurator.max_tokens,
            self.configurator.TPM_limit,
            self.configurator.RPM_limit,
        )

        # 开始循环
        time.sleep(3)
        for current_round in range(self.configurator.round_limit + 1):
            # 检测是否需要停止任务
            if self.configurator.Running_status == self.STATUS.STOPING:
                return {}

            # 译前准备工作
            task_current_round, line_current_round = self.translation_prepare(current_round)

            # 判断是否需要继续翻译
            if line_current_round == 0:
                self.print("")
                self.info("所有文本均已翻译，翻译任务已结束 ...")
                self.print("")
                break

            # 达到最大翻译轮次时
            if line_current_round != 0 and current_round == self.configurator.round_limit:
                self.print("")
                self.warning("已达到最大翻译轮次，仍有部分文本未翻译，请检查结果 ...")
                self.print("")
                break

            # 第一轮时且不是继续翻译时，记录总行数
            if current_round == 0 and translation_continue == False:
                self.data["total_line"] = line_current_round

            # 输出开始翻译的日志
            self.print("")
            self.print("")
            self.info(f"当前轮次 - {current_round + 1}")
            self.info(f"最大轮次 - {self.configurator.round_limit}")
            self.info(f"项目类型 - {self.configurator.translation_project}")
            self.info(f"原文语言 - {self.configurator.source_language}")
            self.info(f"译文语言 - {self.configurator.target_language}")
            self.print("")
            self.info(f"接口名称 - {self.configurator.platforms.get(self.configurator.target_platform, {}).get("name", "未知")}")
            self.info(f"接口地址 - {self.configurator.base_url}")
            self.info(f"模型名称 - {self.configurator.model}")
            self.print("")
            self.info(f"生效中的 RPM 限额 - {self.configurator.RPM_limit}")
            self.info(f"生效中的 TPM 限额 - {self.configurator.TPM_limit}")
            self.info(f"生效中的 MAX_TOKENS 限额 - {self.configurator.max_tokens}")
            self.print("")
            if self.configurator.target_platform != "sakura":
                self.info(f"本次任务使用以下基础指令：\n{self.configurator.get_system_prompt()}")
                self.print("")
            self.info(f"即将开始执行翻译任务，预计任务总数为 {task_current_round}, 同时执行的任务数量为 {self.configurator.actual_thread_counts}，请注意保持网络通畅 ...")
            self.print("")
            self.print("")

            # 开始执行翻译任务
            with concurrent.futures.ThreadPoolExecutor(max_workers = self.configurator.actual_thread_counts, thread_name_prefix = "translator") as executor:
                for i in range(task_current_round):
                    future = executor.submit(
                        TranslatorTask(
                            translator = self,
                            configurator = self.configurator,
                            plugin_manager = self.plugin_manager,
                            request_limiter = self.request_limiter,
                        ).start
                    )
                    future.add_done_callback(lambda future: self.task_done_callback(future, executor))

        # 等待可能存在的缓存文件写入请求处理完毕
        time.sleep(self.CACHE_FILE_SAVE_INTERVAL/1000)

        # 译后处理
        self.translation_post_process()

    # 译前准备
    def translation_prepare(self, current_round: int):
        # 根据混合翻译设置更换翻译平台
        if current_round == 0 and self.configurator.mix_translation_enable:
            self.configurator.target_platform = self.configurator.mix_translation_settings.get("translation_platform_1")

        # 第二轮开始对半切分
        if current_round > 0:
            self.configurator.lines_limit, self.configurator.tokens_limit = self.update_task_limit(
                self.configurator.lines_limit,
                self.configurator.tokens_limit,
            )

        # 配置翻译平台信息
        self.configurator.configure_translation_platform(
            self.configurator.target_platform,
            None,
        )

        # 计算待翻译的文本总行数，tokens总数
        untranslated_text_line_count, untranslated_text_tokens_count = Cache_Manager.count_and_update_translation_status_0_2(
            self,
            self.configurator.cache_list,
        )

        # 计算剩余任务数
        total_tasks = self.calculate_total_tasks(
            untranslated_text_line_count,
            untranslated_text_tokens_count,
            self.configurator.lines_limit,
            self.configurator.tokens_limit,
            self.configurator.tokens_limit_switch,
        )

        return total_tasks, untranslated_text_line_count

    # 译后处理
    def translation_post_process(self):
        # 调用插件，进行文本后处理
        self.plugin_manager.broadcast_event(
            "postprocess_text",
            self.configurator,
            self.configurator.cache_list
        )

        # 如果开启了转换简繁开关功能，则进行文本转换
        if self.configurator.response_conversion_toggle:
            with self.cache_data_lock:
                self.configurator.cache_list = Cache_Manager.simplified_and_traditional_conversion(
                        self,
                        self.configurator.cache_list,
                        self.configurator.opencc_preset,
                    )
                self.print("")
                self.info(f"已启动自动简繁转换功能，正在使用 {self.configurator.opencc_preset} 配置进行字形转换 ...")
                self.print("")

        # 广播翻译完成事件
        self.plugin_manager.broadcast_event(
            "translation_completed",
            self.configurator,
            None
        )

        # 将翻译结果写为对应文件
        File_Outputter.output_translated_content(
            self,
            self.configurator.cache_list,
            self.configurator.label_output_path,
            self.configurator.label_input_path,
        )

        self.print("")
        self.info("翻译结果已保存至指定的输出目录 ...")
        self.print("")

    # 翻译任务完成时
    def task_done_callback(self, future, executor):
        try:
            # 翻译状态文本
            if self.configurator.Running_status == self.STATUS.IDLE:
                status = "无任务"

            if self.configurator.Running_status == self.STATUS.API_TEST:
                status = "测试中"

            if self.configurator.Running_status == self.STATUS.TRANSLATION:
                status = "翻译中"

            if self.configurator.Running_status == self.STATUS.STOPING:
                status = "停止中"

            # 获取结果
            result = future.result()

            # 记录数据
            with self.lock:
                if result.get("check_result") == True:
                    new = {}
                    new["status"] = status
                    new["start_time"] = self.data.get("start_time")
                    new["total_line"] = self.data.get("total_line")
                    new["line"] = self.data.get("line") + result.get("row_count", 0)
                    new["remaining_line"] = new.get("total_line") - new.get("line")
                    new["token"] = self.data.get("token") + result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
                    new["total_completion_tokens"] = self.data.get("total_completion_tokens") + result.get("completion_tokens")
                    new["time"] = time.time() - self.data.get("start_time")
                    new["remaining_time"] = new.get("time") / max(1, new.get("line")) * new.get("remaining_line")
                    new["speed"] = new.get("total_completion_tokens") / max(1, new.get("time"))
                    new["task"] = len([t for t in threading.enumerate() if "translator" in t.name])
                    self.data = new
                else:
                    new = {}
                    new["status"] = status
                    new["start_time"] = self.data.get("start_time")
                    new["total_line"] = self.data.get("total_line")
                    new["line"] = self.data.get("line")
                    new["remaining_line"] = self.data.get("remaining_line")
                    new["token"] = self.data.get("token") + result.get("prompt_tokens", 0) + result.get("completion_tokens", 0)
                    new["total_completion_tokens"] = self.data.get("total_completion_tokens")
                    new["time"] = time.time() - self.data.get("start_time")
                    new["remaining_time"] = new.get("time") / max(1, new.get("line")) * new.get("remaining_line")
                    new["speed"] = new.get("total_completion_tokens") / max(1, new.get("time"))
                    new["task"] = len([t for t in threading.enumerate() if "translator" in t.name])
                    self.data = new

            # 更新翻译进度到缓存数据
            with self.cache_data_lock:
                if len(self.configurator.cache_list) > 0:
                    self.configurator.cache_list[0]["data"] = self.data

            # 请求保存缓存文件
            self.save_cache_file_require()

            # 更新 UI
            self.emit(self.EVENT.TRANSLATION_UPDATE, self.data)
        except Exception as e:
            self.error("翻译任务错误 ...", e)

    # 更新任务长度限制
    def update_task_limit(self, line_limits: int, token_limits: int):
        return max(1, int(line_limits / 2)), max(1, int(token_limits / 2))

    # 请求保存缓存文件
    def save_cache_file_require(self):
        self.save_cache_file_require_flag = True

    # 定时保存缓存文件
    def save_cache_file_tick(self):
        while True:
            time.sleep(self.CACHE_FILE_SAVE_INTERVAL / 1000)
            if hasattr(self, "save_cache_file_require_flag") and self.save_cache_file_require_flag == True:
                self.save_cache_file_require_flag = False
                with self.cache_file_lock:
                    # 创建文件夹
                    folder_path = f"{self.configurator.label_output_path}/cache"
                    os.makedirs(folder_path, exist_ok = True)

                    # 缓存文件路径
                    file_path = f"{folder_path}/AinieeCacheData.json"
                    file_bak_path = f"{folder_path}/AinieeCacheData_bak.json"

                    # 移除旧的备份
                    os.remove(file_bak_path) if os.path.exists(file_bak_path) else None

                    # 备份旧的文件
                    os.rename(file_path, file_bak_path) if os.path.exists(file_path) else None

                    # 保存新的缓存文件
                    self.save_cache_file(
                        self.configurator.cache_list,
                        file_path
                    )

                    # 触发事件
                    self.emit(self.EVENT.CACHE_FILE_AUTO_SAVE, {})

    # 保存缓存文件
    def save_cache_file(self, cache, path):
        new = copy.deepcopy(cache)

        # 更新翻译状态，将翻译中的条目修改为待翻译
        for item in new:
            if item.get("translation_status", 0) == 2:
                item["translation_status"] = 0

        # 写入缓存文件
        with open(path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(new, indent = 4, ensure_ascii = False))

    # 读取缓存文件
    def load_cache_file(self, path):
        cache = []

        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                cache = json.load(reader)

        return cache

    # 计算剩余任务总数
    def calculate_total_tasks(self, total_lines, total_tokens, lines_limit, tokens_limit, switch):
        if switch:
            if total_tokens <= tokens_limit:  # 防止负数计算
                return 1

            if total_tokens % tokens_limit == 0:
                total_tasks = total_tokens // tokens_limit
            else:
                total_tasks = total_tokens // tokens_limit + 1
        else:
            if total_lines % lines_limit == 0:
                total_tasks = total_lines // lines_limit
            else:
                total_tasks = total_lines // lines_limit + 1

        return total_tasks