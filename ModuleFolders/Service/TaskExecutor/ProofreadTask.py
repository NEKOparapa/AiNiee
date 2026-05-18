import concurrent.futures
from collections import defaultdict

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Infrastructure.RequestLimiter.RequestLimiter import RequestLimiter
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus


class ProofreadTask(ConfigMixin, LogMixin, Base):
    MAX_REQUEST_ATTEMPTS = 2  # 单条数据最大重试次数

    def __init__(self, task_data: dict, set_active_executor, clear_active_executor) -> None:
        super().__init__()
        self.task_data = task_data or {}
        self._set_active_executor = set_active_executor
        self._clear_active_executor = clear_active_executor
        self.config = TaskConfig()
        self.request_limiter = RequestLimiter()

    def run(self) -> None:
        try:
            # 1. 解析任务数据
            proofread_jobs = self._normalize_jobs(self.task_data)
            if not proofread_jobs:
                self._finish()
                return

            # 2. 初始化配置和限速器
            self.config.initialize("proofread")
            self.config.prepare_for_active_platform("proofread")
            self.request_limiter.set_limit(self.config.rpm_limit)

            # 3. 展平任务：将所有需要校对的行转为独立的单个任务 (1行 = 1请求)
            single_tasks = self._flatten_jobs(proofread_jobs)
            total_items = len(single_tasks)
            if not total_items:
                self._finish()
                return

            self.info("开始执行 AI 自动校对任务 ...")
            self.info(
                "校对配置：共 {0} 个文件，{1} 条内容，并发线程 {2}，单条最多重试 {3} 次。".format(
                    len(proofread_jobs),
                    total_items,
                    self.config.actual_thread_counts,
                    self.MAX_REQUEST_ATTEMPTS,
                )
            )

            updates_by_file = defaultdict(dict)
            success_count = 0
            failed_count = 0
            processed_count = 0
            progress_interval = self._get_progress_interval(total_items)

            # 4. 并发执行单行校对任务
            executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.actual_thread_counts,
                thread_name_prefix="proofreader",
            )
            self._set_active_executor(executor)

            try:
                futures = []
                for idx, task_info in enumerate(single_tasks, start=1):
                    if Base.work_status == Base.STATUS.STOPING:
                        break
                    # 注入当前任务的进度索引信息，方便打印日志
                    task_info["task_idx"] = idx
                    task_info["total_tasks"] = total_items
                    futures.append(executor.submit(self._run_single_item, task_info))

                for future in concurrent.futures.as_completed(futures):
                    if Base.work_status == Base.STATUS.STOPING:
                        break
                        
                    try:
                        result = future.result()
                    except concurrent.futures.CancelledError:
                        continue
                    except Exception as error:
                        self.error(f"单条校对任务执行异常：{error}")
                        failed_count += 1
                        processed_count += 1
                        self._log_progress(processed_count, total_items, success_count, failed_count, progress_interval)
                        continue

                    if not result:
                        failed_count += 1
                        processed_count += 1
                        self._log_progress(processed_count, total_items, success_count, failed_count, progress_interval)
                        continue

                    success_count += 1
                    processed_count += 1
                    file_path = result["file_path"]
                    text_index = result["text_index"]
                    corrected_text = result["corrected_text"]
                    
                    updates_by_file[file_path][text_index] = corrected_text
                    self._log_progress(processed_count, total_items, success_count, failed_count, progress_interval)

            finally:
                try:
                    executor.shutdown(wait=True, cancel_futures=Base.work_status == Base.STATUS.STOPING)
                finally:
                    self._clear_active_executor(executor)

            self.info("AI 自动校对处理完成：成功 {0} 条，失败 {1} 条。".format(success_count, failed_count))
            
            # 5. 触发更新事件落盘
            self._emit_updates(updates_by_file)
            self._emit_done_event(updates_by_file, success_count, failed_count)
            self._finish()
            
        except Exception as error:
            self.error(f"AI 自动校对任务执行失败：{error}", error)
            Base.work_status = Base.STATUS.IDLE
            raise

    def _normalize_jobs(self, data: dict) -> list[dict]:
        """标准化前端传来的数据结构"""
        proofread_jobs = data.get("proofread_jobs")
        if not isinstance(proofread_jobs, list):
            file_path = data.get("file_path")
            items_to_proofread = data.get("items_to_proofread")
            if file_path and isinstance(items_to_proofread, list):
                proofread_jobs = [{"file_path": file_path, "items_to_proofread": items_to_proofread}]
            else:
                proofread_jobs = []

        normalized_jobs = []
        for job in proofread_jobs:
            if not isinstance(job, dict): continue
            file_path = job.get("file_path")
            items_to_proofread = job.get("items_to_proofread")
            if not file_path or not isinstance(items_to_proofread, list): continue

            normalized_items = []
            for item in items_to_proofread:
                if not isinstance(item, dict): continue
                text_index = item.get("text_index")
                source_text = item.get("source_text", "")
                if text_index is None or source_text is None: continue

                normalized_items.append({
                    "text_index": text_index,
                    "source_text": str(source_text),
                    "translation_text": str(item.get("translation_text", "") or ""),
                    "error_type": str(item.get("error_type", "") or ""),
                })

            if normalized_items:
                normalized_jobs.append({"file_path": file_path, "items_to_proofread": normalized_items})

        return normalized_jobs

    def _flatten_jobs(self, proofread_jobs: list[dict]) -> list[dict]:
        """将多文件的批次结构展平为独立的单条任务列表"""
        single_tasks = []
        for job in proofread_jobs:
            file_path = job["file_path"]
            for item in job["items_to_proofread"]:
                single_tasks.append({
                    "file_path": file_path,
                    "item": item
                })
        return single_tasks

    def _run_single_item(self, task_info: dict) -> dict | None:
        """执行单条校对任务，带重试机制"""
        if Base.work_status == Base.STATUS.STOPING:
            return None

        file_path = task_info["file_path"]
        item = task_info["item"]
        task_idx = task_info["task_idx"]
        total_tasks = task_info["total_tasks"]
        
        text_index = item["text_index"]
        
        current_platform_config = self.config.get_active_platform_configuration("proofread")
        messages, system_prompt = self._build_single_proofread_prompt(item)

        last_error = ""
        # 重试流水线
        for attempt in range(1, self.MAX_REQUEST_ATTEMPTS + 1):
            if Base.work_status == Base.STATUS.STOPING:
                return None

            try:
                requester = LLMRequester()
                skip, _, response_content, _, _ = requester.sent_request(
                    messages,
                    system_prompt,
                    current_platform_config,
                )

                if skip:
                    last_error = "请求被跳过或接口返回错误"
                    continue

                response_content = str(response_content or "").strip()
                
                # 简单清洗，防止 AI 输出 Markdown 代码块包裹
                if response_content.startswith("```"):
                    response_content = "\n".join(response_content.split("\n")[1:])
                if response_content.endswith("```"):
                    response_content = "\n".join(response_content.split("\n")[:-1])
                response_content = response_content.strip()

                if not response_content:
                    last_error = "模型返回内容为空"
                    continue

                return {
                    "file_path": file_path,
                    "text_index": text_index,
                    "corrected_text": response_content,
                }

            except Exception as e:
                last_error = str(e)

            # 打印重试日志
            if attempt < self.MAX_REQUEST_ATTEMPTS:
                self.warning(
                    "校对任务 {0}/{1} 第 {2} 次请求失败，准备重试。原因：{3}".format(
                        task_idx,
                        total_tasks,
                        attempt,
                        last_error,
                    )
                )
            else:
                self.error(
                    "校对任务 {0}/{1} 失败，已达到最大重试次数。原因：{2}".format(
                        task_idx,
                        total_tasks,
                        last_error,
                    )
                )

        return None

    def _build_single_proofread_prompt(self, item: dict) -> tuple[list[dict], str]:
            """构建带有 Few-Shot 的单条 Prompt（全中文）"""
            target_language = str(getattr(self.config, "target_language", "") or "").replace("_", " ")
            lang_instruction = target_language if target_language else "当前译文所使用的语言"

            issue_type = item.get("error_type") or "未指定具体问题"
            source_text = item.get("source_text", "")
            translation_text = item.get("translation_text", "")
            translation_display = translation_text if translation_text else "[空]"

            system_prompt = (
                "你是一名专业的翻译校对员。"
                "你将收到一个问题类型、原文和当前译文。你的唯一任务是输出校对修改后的最终译文。\n"
                "【关键规则】\n"
                "1. 只能输出校对后的译文文本，绝不要输出任何多余的文字。\n"
                "2. 不要提供任何解释、道歉，也不要使用 markdown 代码块（如 ```）包裹内容。\n"
                "3. 严格保留原文中的占位符、变量、标签、转义字符、换行符和特殊格式。\n"
                "4. 如果当前译文为空、缺失或质量极其糟糕，请直接根据原文进行重新翻译。"
            )

            # 引入 Few-Shot (少样本示例)，通过对话历史规训AI的输出格式
            fake_user_1 = (
                f"目标语言：{lang_instruction}\n"
                f"问题类型：标签缺失\n"
                f"原文：\nHello <b>World</b>\n"
                f"当前译文：\n你好 World\n"
                f"---\n请输出校对后的最终译文："
            )
            fake_assistant_1 = "你好 <b>World</b>"

            fake_user_2 = (
                f"目标语言：{lang_instruction}\n"
                f"问题类型：占位符不匹配\n"
                f"原文：\nDamage: {{dmg_val}} points\n"
                f"当前译文：\n伤害：{{damage}}点\n"
                f"---\n请输出校对后的最终译文："
            )
            fake_assistant_2 = "伤害：{dmg_val}点"

            # 真实请求
            user_prompt = (
                f"目标语言：{lang_instruction}\n"
                f"问题类型：{issue_type}\n"
                f"原文：\n{source_text}\n"
                f"当前译文：\n{translation_display}\n"
                f"---\n请输出校对后的最终译文："
            )

            messages = [
                {"role": "user", "content": fake_user_1},
                {"role": "assistant", "content": fake_assistant_1},
                {"role": "user", "content": fake_user_2},
                {"role": "assistant", "content": fake_assistant_2},
                {"role": "user", "content": user_prompt},
            ]

            return messages, system_prompt

    def _emit_updates(self, updates_by_file: dict) -> None:
        """向主线程/UI发射更新事件"""
        updated_file_count = 0
        updated_item_count = 0
        update_event = self.task_data.get("update_event", Base.EVENT.TABLE_UPDATE)
        for file_path, updated_items in updates_by_file.items():
            if not updated_items:
                continue

            updated_file_count += 1
            updated_item_count += len(updated_items)
            self.emit(
                update_event,
                {
                    "file_path": file_path,
                    "target_column_index": 2, # 通常2为翻译列
                    "translation_status": TranslationStatus.POLISHED,
                    "updated_items": dict(updated_items),
                },
            )

        if updated_item_count > 0:
            self.info("校对结果已回写：共更新 {0} 个文件，{1} 条内容。".format(updated_file_count, updated_item_count))

    def _emit_done_event(self, updates_by_file: dict, success_count: int, failed_count: int) -> None:
        done_event = self.task_data.get("done_event")
        if done_event is None:
            return

        updated_file_count = 0
        updated_item_count = 0
        file_paths = []
        for file_path, updated_items in updates_by_file.items():
            if not updated_items:
                continue

            updated_file_count += 1
            updated_item_count += len(updated_items)
            file_paths.append(file_path)

        self.emit(
            done_event,
            {
                "operation": "proofread",
                "status": "success" if updated_item_count > 0 else "empty",
                "updated_file_count": updated_file_count,
                "updated_item_count": updated_item_count,
                "success_count": success_count,
                "failed_count": failed_count,
                "file_paths": file_paths,
            },
        )

    def _finish(self) -> None:
        """收尾状态更新"""
        if Base.work_status == Base.STATUS.STOPING:
            Base.work_status = Base.STATUS.TASKSTOPPED
            self.info("AI 自动校对任务已停止。")
        else:
            Base.work_status = Base.STATUS.IDLE
            self.info("AI 自动校对任务已结束。")

    def _get_progress_interval(self, total_items: int) -> int:
        if total_items <= 10:
            return 1
        return max(5, total_items // 5)

    def _log_progress(
        self,
        processed_count: int,
        total_items: int,
        success_count: int,
        failed_count: int,
        progress_interval: int,
    ) -> None:
        if processed_count != total_items and processed_count % progress_interval != 0:
            return

        self.info(
            "校对进度：{0}/{1}，成功 {2} 条，失败 {3} 条。".format(
                processed_count,
                total_items,
                success_count,
                failed_count,
            )
        )
