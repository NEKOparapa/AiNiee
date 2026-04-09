import concurrent.futures
import re
from datetime import datetime

import rapidjson as json

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Infrastructure.RequestLimiter.RequestLimiter import RequestLimiter
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Infrastructure.Tokener.Tokener import Tokener


class AnalysisTask(ConfigMixin, LogMixin, Base):
    """
    数据流概览：
    1. 先从 cache_manager 按 token 切出原文分块，每个分块仍然保留原文上下文。
    2. 第一阶段对每个分块独立请求 AI，尽量多抽出 characters/terms/non_translate 候选。
    3. 把第一阶段的 characters/terms 先按原始 source 去重收集，再按最长 source 优先把“被它包含的短 source”吸进同一组。
    4. 第二阶段让 AI 在每个候选组内做一次裁决：这个 source 最终属于角色还是术语，以及保留什么译名和备注。
    5. 主线程统一收口第二阶段结果；若某些组没返回，则用本地规则兜底。
    6. non_translate 不走第二阶段，只在最后做去重和过滤，然后整体写回缓存并落盘。
    """
    # 第一阶段按原文分块抽取候选；第二阶段按同一个 source 聚合后再让 AI 做合并判断。
    CHUNK_TOKEN_LIMIT = 10000
    REDUCE_BATCH_TOKEN_LIMIT = 10000
    MAX_REQUEST_ATTEMPTS = 2
    COMMON_PUNCTUATION_CHARS = set(
        ".,!?;:'\"-_=+~`^…—、，。！？；：‘’“”()（）[]【】{}《》<>「」『』〈〉〔〕﹝﹞·•/\\|"
    )

    def __init__(self, cache_manager, set_active_executor, clear_active_executor) -> None:
        super().__init__()
        self.cache_manager = cache_manager
        self._set_active_executor = set_active_executor
        self._clear_active_executor = clear_active_executor
        self.config = TaskConfig()
        self.request_limiter = RequestLimiter()
        # 保存第二阶段的聚合输入，供最终阶段在 AI 没返回某些词时做程序兜底。
        self.grouped_stage_two_inputs = {}
        # 保存第二阶段的 source 别名到主 source 的映射，防止 AI 返回被吸收的短 source。
        self.grouped_stage_two_source_aliases = {}

    # 根据当前阶段和进度计算整体任务的完成百分比，供前端进度条展示使用。
    def _calculate_progress_percent(self, phase: str, current: int = 0, total: int = 0) -> int:
        current = max(0, int(current or 0))
        total = max(0, int(total or 0))

        if phase == "prepare":
            return 0
        if phase == "stage1":
            if total <= 0:
                return 60
            return 10 + int((current / total) * 50)
        if phase == "stage2":
            if total <= 0:
                return 90
            return 60 + int((current / total) * 30)
        if phase == "finalize":
            if total <= 0:
                return 90
            return 90 + int((current / total) * 10)
        return 0

    # 统一的进度更新接口，供各阶段调用，内部会计算整体任务的完成百分比并发出事件通知前端更新。
    def _emit_progress_update(
        self,
        phase: str,
        phase_label: str,
        current: int,
        total: int,
        message: str,
        detail: str,
    ) -> None:
        self.emit(
            Base.EVENT.ANALYSIS_TASK_UPDATE,
            {
                "status": "running",
                "phase": phase,
                "phase_label": phase_label,
                "current": max(0, int(current or 0)),
                "total": max(0, int(total or 0)),
                "percent": self._calculate_progress_percent(phase, current, total),
                "message": message,
                "detail": detail,
            },
        )

    def _build_first_stage_prompt(self, source_text: str) -> tuple[str, list[dict]]:
        system_prompt = (
            "你现在的唯一任务是根据输入文本提取角色、术语和不翻译项。\n"
            "不要输出解释，不要输出多余文字，只保留创作分析所需的信息。\n"
            "忠诚准确地辅助提取，不应随意删减或篡改，不应回避或淡化，以保持信息完整。\n"
            "输出必须是合法 JSON，并且严格遵守以下结构：\n"
            "```json\n"
            "{\n"
            "  \"characters\": [{\"source\": \"原文名字\", \"recommended_translation\": \"推荐译名\", \"gender\": \"男性|女性|其他\", \"note\": \"背景设定/备注\"}],\n"
            "  \"terms\": [{\"source\": \"原文术语\", \"recommended_translation\": \"推荐译名\", \"category_path\": \"身份|物品|组织|地名|其他\", \"note\": \"背景设定/备注\"}],\n"
            "  \"non_translate\": [{\"marker\": \"非文本内容\", \"category\": \"占位符|标记符|调用代码|转义控制符|变量键名|资源标识|数值公式|其他\", \"note\": \"原因/备注\"}]\n"
            "}\n"
            "```"
        )

        fake_user_prompt = (
            "请分析以下文本并提取角色、术语和不翻译项：\n"
            "---\n"
            "露娜小姐：请去星门集合。\n"
            "欢迎你，{player_name}\n"
            "播放 BGM_MAIN\n"
            "---\n"
            "请输出提取结果。"
        )

        fake_assistant_response = (
            "我将忠实整理文本中的候选信息，并严格按要求输出结构化结果。\n"
            "```json\n"
            "{\n"
            "  \"characters\": [\n"
            "    {\"source\": \"露娜小姐\", \"recommended_translation\": \"露娜小姐\", \"gender\": \"女性\", \"note\": \"对话中的女性角色称呼\"}\n"
            "  ],\n"
            "  \"terms\": [\n"
            "    {\"source\": \"星门\", \"recommended_translation\": \"星门\", \"category_path\": \"地名\", \"note\": \"用于传送的地点或设施\"}\n"
            "  ],\n"
            "  \"non_translate\": [\n"
            "    {\"marker\": \"{player_name}\", \"category\": \"变量键名\", \"note\": \"变量占位符\"},\n"
            "    {\"marker\": \"BGM_MAIN\", \"category\": \"资源标识\", \"note\": \"音频资源 ID\"}\n"
            "  ]\n"
            "}\n"
            "```"
        )

        user_prompt = (
            "请分析以下文本并提取角色、术语和不翻译项：\n"
            "---\n"
            f"{source_text}\n"
            "---\n"
            "请输出提取结果。"
        )

        assistant_prefix = "我将忠实整理文本中的候选信息，并严格按要求输出结构化结果。\n```json\n"

        messages = [
            {"role": "user", "content": fake_user_prompt},
            {"role": "assistant", "content": fake_assistant_response},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_prefix},
        ]

        return system_prompt, messages

    def _build_second_stage_prompt(self, batch: list) -> tuple[str, list[dict]]:
        system_prompt = (
            "你现在的唯一任务是对候选组进行归并裁决，判断每个 group 最终属于角色还是术语。\n"
            "不要输出解释，不要输出多余文字，只保留创作分析所需的信息。\n"
            "必须综合同一组中的全部候选，输出最合理的归类、译名与备注。\n"
            "输出必须是合法 JSON，并且严格遵守以下结构：\n"
            "```json\n"
            "{\n"
            "  \"characters\": [{\"source\": \"主source\", \"recommended_translation\": \"推荐译名\", \"gender\": \"男性|女性|其他\", \"note\": \"备注\"}],\n"
            "  \"terms\": [{\"source\": \"主source\", \"recommended_translation\": \"推荐译名\", \"category_path\": \"身份|物品|组织|地名|其他\", \"note\": \"备注\"}]\n"
            "}\n"
            "```\n"
            "输出时 source 必须使用每个 group 的主 source，不要输出 merged_sources 或 candidate_source 中的短 source。"
        )

        example_batch = [
            {
                "source": "露娜小姐",
                "merged_sources": ["露娜小姐", "露娜"],
                "candidates": [
                    {
                        "candidate_source": "露娜小姐",
                        "type": "character",
                        "recommended_translation": "露娜小姐",
                        "gender": "女性",
                        "category_path": "",
                        "note": "女性角色的正式称呼",
                    },
                    {
                        "candidate_source": "露娜",
                        "type": "character",
                        "recommended_translation": "露娜",
                        "gender": "女性",
                        "category_path": "",
                        "note": "同一角色的简称",
                    },
                    {
                        "candidate_source": "露娜",
                        "type": "term",
                        "recommended_translation": "月神",
                        "gender": "",
                        "category_path": "其他",
                        "note": "误提取为术语",
                    },
                ],
            },
            {
                "source": "星门",
                "merged_sources": ["星门"],
                "candidates": [
                    {
                        "candidate_source": "星门",
                        "type": "term",
                        "recommended_translation": "星门",
                        "gender": "",
                        "category_path": "地名",
                        "note": "用于传送的地点或设施",
                    },
                    {
                        "candidate_source": "星门",
                        "type": "character",
                        "recommended_translation": "星门",
                        "gender": "其他",
                        "category_path": "",
                        "note": "误提取为角色",
                    },
                ],
            },
        ]

        fake_user_prompt = (
            "请分析以下候选组并完成合并裁决：\n"
            "---\n"
            f"{json.dumps(example_batch, ensure_ascii=False)}\n"
            "---\n"
            "请输出合并结果。"
        )

        fake_assistant_response = (
            "我将忠实整理每个候选组，并只保留最终裁决结果。\n"
            "```json\n"
            "{\n"
            "  \"characters\": [\n"
            "    {\"source\": \"露娜小姐\", \"recommended_translation\": \"露娜小姐\", \"gender\": \"女性\", \"note\": \"与简称‘露娜’是同一角色，保留正式称呼\"}\n"
            "  ],\n"
            "  \"terms\": [\n"
            "    {\"source\": \"星门\", \"recommended_translation\": \"星门\", \"category_path\": \"地名\", \"note\": \"用于传送的地点或设施\"}\n"
            "  ]\n"
            "}\n"
            "```"
        )

        user_prompt = (
            "请分析以下候选组并完成合并裁决：\n"
            "---\n"
            f"{json.dumps(batch, ensure_ascii=False)}\n"
            "---\n"
            "请输出合并结果。"
        )

        assistant_prefix = "我将忠实整理每个候选组，并只保留最终裁决结果。\n```json\n"

        messages = [
            {"role": "user", "content": fake_user_prompt},
            {"role": "assistant", "content": fake_assistant_response},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_prefix},
        ]

        return system_prompt, messages

    # 解析 AI 回复中的 JSON 内容，兼容可能的多余文字或格式问题。
    def _validate_required_list_fields(self, parsed: dict | None, required_fields: tuple[str, ...]) -> tuple[bool, str]:
        if not isinstance(parsed, dict):
            return False, "未返回有效 JSON 对象"

        for field_name in required_fields:
            if field_name not in parsed:
                return False, f"缺少字段 {field_name}"
            if not isinstance(parsed.get(field_name), list):
                return False, f"字段 {field_name} 不是数组"

        return True, ""

    # 只保留 required_fields 中的字段，并保证它们都是列表，其他字段全部丢弃。
    def _normalize_response_payload(self, parsed: dict, fields: tuple[str, ...]) -> dict:
        return {field_name: list(parsed.get(field_name) or []) for field_name in fields}

    # 第一阶段的验证只检查字段结构，第二阶段则需要结合输入 batch 做更严格的语义校验。
    def _validate_first_stage_response(self, parsed: dict | None) -> tuple[bool, str]:
        return self._validate_required_list_fields(parsed, ("characters", "terms", "non_translate"))

    # 第二阶段的验证除了检查字段结构，还要确保至少返回了一个 group 结果，除非输入 batch 本身就是空的。
    def _validate_second_stage_response(self, parsed: dict | None, batch: list) -> tuple[bool, str]:
        is_valid, reason = self._validate_required_list_fields(parsed, ("characters", "terms"))
        if not is_valid:
            return False, reason

        if batch and not parsed.get("characters") and not parsed.get("terms"):
            return False, "未返回任何 group 结果"

        return True, ""

    # 从 AI 回复中提取 JSON 内容，兼容可能的多余文字或格式问题。
    def _send_analysis_request_with_retry(
        self,
        stage_label: str,
        build_request,
        validate_response,
        normalize_fields: tuple[str, ...],
    ) -> dict | None:
        last_error = "未知错误"

        for attempt in range(1, self.MAX_REQUEST_ATTEMPTS + 1):
            if Base.work_status == Base.STATUS.STOPING:
                return None

            try:
                system_prompt, messages = build_request()
                requester = LLMRequester()
                skip, _, response_content, _, _ = requester.sent_request(
                    [dict(message) for message in messages],
                    system_prompt,
                    self.config.get_active_platform_configuration(),
                )

                if skip:
                    if Base.work_status == Base.STATUS.STOPING:
                        return None
                    last_error = "请求被跳过或接口返回错误"
                else:
                    response_content = str(response_content or "")
                    if not response_content.strip():
                        last_error = "模型回复为空"
                    else:
                        parsed = self._parse_json_from_response(response_content)
                        is_valid, validation_error = validate_response(parsed)
                        if is_valid:
                            return self._normalize_response_payload(parsed, normalize_fields)
                        last_error = validation_error
            except Exception as error:
                if Base.work_status == Base.STATUS.STOPING:
                    return None
                last_error = str(error)

            if attempt < self.MAX_REQUEST_ATTEMPTS:
                self.warning(f"{stage_label} 第 {attempt} 次尝试失败，将重试一次：{last_error}")
            else:
                self.error(f"{stage_label} 第 {attempt} 次尝试失败：{last_error}")

        return None

    # 分析主流程
    def run(self) -> None:
        """
        调度整个分析任务。

        这里的几个关键中间结果分别是：
        - chunks: 原文分块列表，是第一阶段的输入。
        - first_stage_results: 每个分块各自抽出的候选结果列表。
        - reduction_batches: 按“最长 source + 被其包含的短 source”聚合后的候选组批次，是第二阶段的输入。
        - second_stage_results: 第二阶段对每个候选组做完裁决后的结果列表。
        - final_data: 主线程统一合并后的最终标签数据。
        """
        try:
            # 初始化分析任务，并复用当前激活接口配置作为请求参数来源。
            Base.work_status = Base.STATUS.ANALYSIS_TASK
            self._emit_progress_update(
                "prepare",
                "准备中",
                0,
                0,
                "正在初始化分析任务...",
                "正在加载接口配置与限流设置。",
            )

            self.config.initialize()
            self.config.prepare_for_active_platform()
            self.request_limiter.set_limit(self.config.tpm_limit, self.config.rpm_limit)

            # 第一阶段输入仍然是按 token 切分的原文块。
            self._emit_progress_update(
                "prepare",
                "准备中",
                0,
                0,
                "正在生成分析用文本片段...",
                "正在按 token 切分项目原文。",
            )
            chunks = self.cache_manager.generate_analysis_source_chunks("token", self.CHUNK_TOKEN_LIMIT)

            # 第一阶段：并发抽取角色、术语、禁翻候选。
            self._emit_progress_update(
                "stage1",
                "第一阶段",
                0,
                len(chunks),
                f"开始执行第一阶段分析任务，共 {len(chunks)} 个分块...",
                f"已完成 0 / {len(chunks)} 个分块。",
            )
            # first_stage_results 的粒度是“每个 chunk 一份结果”。
            # 这一步允许同一个 source 在不同 chunk 中重复出现，冲突留到第二阶段再消解。
            first_stage_results = []
            executor_stage1 = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.actual_thread_counts,
                thread_name_prefix="analysis_stage1",
            )
            self._set_active_executor(executor_stage1)

            try:
                futures_stage1 = []
                for chunk in chunks:
                    if Base.work_status == Base.STATUS.STOPING:
                        break
                    futures_stage1.append(executor_stage1.submit(self._run_first_stage, chunk))

                total_stage1 = len(futures_stage1)
                completed_stage1 = 0
                for future in concurrent.futures.as_completed(futures_stage1):
                    if Base.work_status == Base.STATUS.STOPING:
                        break
                    result = future.result()
                    if result:
                        first_stage_results.append(result)
                    completed_stage1 += 1
                    self._emit_progress_update(
                        "stage1",
                        "第一阶段",
                        completed_stage1,
                        total_stage1,
                        "第一阶段分析中...",
                        f"已完成 {completed_stage1} / {total_stage1} 个分块。",
                    )
            finally:
                try:
                    executor_stage1.shutdown(
                        wait=True,
                        cancel_futures=Base.work_status == Base.STATUS.STOPING,
                    )
                finally:
                    self._clear_active_executor(executor_stage1)

            if Base.work_status == Base.STATUS.STOPING:
                Base.work_status = Base.STATUS.TASKSTOPPED
                self.emit(
                    Base.EVENT.ANALYSIS_TASK_DONE,
                    {"status": "stopped", "analysis_data": None, "message": "分析任务已停止"},
                )
                return

            # 第二阶段：先按 source 聚合候选，再交给 AI 在组内做归类和合并。
            reduction_batches = self._prepare_reduction_batches(first_stage_results)
            self._emit_progress_update(
                "stage2",
                "第二阶段",
                0,
                len(reduction_batches),
                f"开始执行第二阶段分析任务，共 {len(reduction_batches)} 个合并批次...",
                f"已完成 0 / {len(reduction_batches)} 个合并批次。",
            )

            # second_stage_results 的粒度是“每个 reduction batch 一份结果”。
            # 此时 batch 内的数据已经不是原文 chunk，而是按最长 source 归并过的候选组。
            second_stage_results = []
            if reduction_batches:
                executor_stage2 = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.config.actual_thread_counts,
                    thread_name_prefix="analysis_stage2",
                )
                self._set_active_executor(executor_stage2)

                try:
                    futures_stage2 = []
                    for batch in reduction_batches:
                        if Base.work_status == Base.STATUS.STOPING:
                            break
                        futures_stage2.append(executor_stage2.submit(self._run_second_stage, batch))

                    total_stage2 = len(futures_stage2)
                    completed_stage2 = 0
                    for future in concurrent.futures.as_completed(futures_stage2):
                        if Base.work_status == Base.STATUS.STOPING:
                            break
                        result = future.result()
                        if result:
                            second_stage_results.append(result)
                        completed_stage2 += 1
                        self._emit_progress_update(
                            "stage2",
                            "第二阶段",
                            completed_stage2,
                            total_stage2,
                            "第二阶段分析中...",
                            f"已完成 {completed_stage2} / {total_stage2} 个合并批次。",
                        )
                finally:
                    try:
                        executor_stage2.shutdown(
                            wait=True,
                            cancel_futures=Base.work_status == Base.STATUS.STOPING,
                        )
                    finally:
                        self._clear_active_executor(executor_stage2)

            if Base.work_status == Base.STATUS.STOPING:
                Base.work_status = Base.STATUS.TASKSTOPPED
                self.emit(
                    Base.EVENT.ANALYSIS_TASK_DONE,
                    {"status": "stopped", "analysis_data": None, "message": "分析任务已停止"},
                )
                return

            # 最终在主线程统一收口，避免不同批次的结果互相覆盖。
            self._emit_progress_update(
                "finalize",
                "结果整合",
                0,
                1,
                "正在整合最终分析结果...",
                "正在整合角色、术语和禁翻结果。",
            )
            final_data = self._finalize_results(first_stage_results, second_stage_results)
            self._emit_progress_update(
                "finalize",
                "结果整合",
                1,
                1,
                "分析结果已生成...",
                "正在写回项目缓存。",
            )

            analysis_data = {
                "status": "success",
                "last_run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "characters": final_data.get("characters", []),
                "terms": final_data.get("terms", []),
                "non_translate": final_data.get("non_translate", []),
                "stats": {
                    "character_count": len(final_data.get("characters", [])),
                    "term_count": len(final_data.get("terms", [])),
                    "non_translate_count": len(final_data.get("non_translate", [])),
                    "total_hits": (
                        len(final_data.get("characters", []))
                        + len(final_data.get("terms", []))
                        + len(final_data.get("non_translate", []))
                    ),
                },
            }
            self.cache_manager.set_analysis_data(analysis_data)
            self.cache_manager.require_save_to_file()

            Base.work_status = Base.STATUS.IDLE
            self.emit(
                Base.EVENT.ANALYSIS_TASK_DONE,
                {"status": "success", "analysis_data": analysis_data, "message": "全文分析完成。"},
            )

        except Exception as error:
            self.error(f"分析任务执行失败: {error}", error)
            Base.work_status = Base.STATUS.IDLE
            self.emit(
                Base.EVENT.ANALYSIS_TASK_DONE,
                {"status": "error", "analysis_data": None, "message": str(error)},
            )

    # 第一阶段的处理函数，输入是一个原文 chunk，输出是该 chunk 的抽取结果。
    def _run_first_stage(self, chunk: list) -> dict:
        try:
            source_text = "\n".join(item.get("source_text", "") for item in chunk)
            result = self._send_analysis_request_with_retry(
                "第一阶段提取",
                lambda: self._build_first_stage_prompt(source_text),
                self._validate_first_stage_response,
                ("characters", "terms", "non_translate"),
            )
            if result is not None:
                return result
        except Exception as error:
            self.error(f"第一阶段提取失败: {error}")

        return {"characters": [], "terms": [], "non_translate": []}

    # 第二阶段的处理函数，输入是一个候选组 batch，输出是该 batch 的合并结果。
    def _prepare_reduction_batches(self, first_stage_results: list) -> list:
        """
        把第一阶段的分块级结果重排成第二阶段可消费的“同词候选组”。

        输入是:
        - first_stage_results: 多个 chunk 的抽取结果。

        输出是:
        - batches: 每个 batch 由多个 group 组成；
          每个 group 结构为 {"source": "...", "merged_sources": [...], "candidates": [...]}，
          其中 source 是最长的主 source，merged_sources 记录被并入该组的短 source，
          candidates 则收集这些 source 在不同 chunk 中出现过的所有角色/术语候选。
          batch 的切分方式参考 CacheManager：按 token 累加，超过上限就换批，
          但每个 batch 至少会保留一个 group。
        """
        # 先把角色表、术语表按“原始 source 完全相同”聚成组。
        # 这一步还不做长短 source 的吸收，只负责保留原始候选。
        raw_grouped_inputs = {}

        for result in first_stage_results:
            for row in result.get("characters", []):
                source = str(row.get("source", "")).strip()
                if not source:
                    continue
                raw_grouped_inputs.setdefault(source, {"source": source, "merged_sources": [source], "candidates": []})
                raw_grouped_inputs[source]["candidates"].append(
                    {
                        "candidate_source": source,
                        "type": "character",
                        "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                        "gender": str(row.get("gender", "")).strip(),
                        "category_path": "",
                        "note": str(row.get("note", "")).strip(),
                    }
                )

            for row in result.get("terms", []):
                source = str(row.get("source", "")).strip()
                if not source:
                    continue
                raw_grouped_inputs.setdefault(source, {"source": source, "merged_sources": [source], "candidates": []})
                raw_grouped_inputs[source]["candidates"].append(
                    {
                        "candidate_source": source,
                        "type": "term",
                        "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                        "gender": "",
                        "category_path": str(row.get("category_path", "")).strip(),
                        "note": str(row.get("note", "")).strip(),
                    }
                )

        # 再按 source 长度倒序做一次归并：
        # - 先处理最长的 source，把“被当前 source 包含”的更短 source 吸进当前组。
        # - 一旦短 source 被吸收，就不再单独建组。
        sorted_sources = sorted(raw_grouped_inputs.keys(), key=lambda source: (-len(source), source))
        grouped_inputs = {}
        source_aliases = {}
        consumed_sources = set()

        for source in sorted_sources:
            if source in consumed_sources:
                continue

            merged_group = {
                "source": source,
                "merged_sources": [source],
                "candidates": list(raw_grouped_inputs[source].get("candidates", [])),
            }
            grouped_inputs[source] = merged_group
            source_aliases[source] = source
            consumed_sources.add(source)

            for other_source in sorted_sources:
                if other_source in consumed_sources:
                    continue
                if other_source == source:
                    continue
                if self._is_source_part_of(source, other_source):
                    merged_group["merged_sources"].append(other_source)
                    merged_group["candidates"].extend(raw_grouped_inputs[other_source].get("candidates", []))
                    source_aliases[other_source] = source
                    consumed_sources.add(other_source)

        self.grouped_stage_two_inputs = grouped_inputs
        self.grouped_stage_two_source_aliases = source_aliases

        # 先按最长 source 排序，其次按候选量排序。
        # 批次切分参考 CacheManager 的 token 模式：
        # - 先计算每个 group 的 token 数；
        # - 如果加入后会超过上限，就先提交当前 batch；
        # - 即使单个 group 自身超过上限，也仍然单独成批，保证每批至少一个 group。
        grouped_items = list(grouped_inputs.values())
        grouped_items.sort(key=lambda item: (-len(item["source"]), -len(item["candidates"]), item["source"]))

        batches = []
        current_batch = []
        current_tokens = 0
        for item in grouped_items:
            item_tokens = self._get_group_token_count(item)
            if current_batch and (current_tokens + item_tokens > self.REDUCE_BATCH_TOKEN_LIMIT):
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(item)
            current_tokens += item_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    # 第二阶段的处理函数，输入是一个候选组 batch，输出是该 batch 的合并结果。
    def _run_second_stage(self, batch: list) -> dict:
        try:
            result = self._send_analysis_request_with_retry(
                "第二阶段合并",
                lambda: self._build_second_stage_prompt(batch),
                lambda parsed: self._validate_second_stage_response(parsed, batch),
                ("characters", "terms"),
            )
            if result is not None:
                return result
        except Exception as error:
            self.error(f"第二阶段合并失败: {error}")

        return {"characters": [], "terms": []}

    # 最终收口函数，输入是第一阶段的分块结果列表和第二阶段的合并结果列表，输出是最终的角色/术语/禁翻数据。
    def _finalize_results(self, first_stage_results: list, second_stage_results: list) -> dict:
        """
        在主线程做最终收口，保证不同批次之间不会互相覆盖。

        合并顺序是：
        1. 先信任第二阶段 AI 的正式裁决结果。
        2. 再用 grouped_stage_two_inputs 对缺失的 source 做本地兜底。
        3. 最后单独处理 non_translate 的去重与过滤。
        """
        # 先吸收第二阶段 AI 的正式结果，并保证同一个 source 只落到一个表里。
        merged_characters = {}
        merged_terms = {}
        assigned_sources = set()

        for result in second_stage_results:
            for row in result.get("characters", []):
                source = self._canonicalize_group_source(row.get("source", ""))
                if not source or source in assigned_sources:
                    continue
                merged_characters[source] = {
                    "source": source,
                    "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                    "gender": str(row.get("gender", "")).strip() or "其他",
                    "note": str(row.get("note", "")).strip(),
                }
                assigned_sources.add(source)

            for row in result.get("terms", []):
                source = self._canonicalize_group_source(row.get("source", ""))
                if not source or source in assigned_sources:
                    continue
                merged_terms[source] = {
                    "source": source,
                    "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                    "category_path": str(row.get("category_path", "")).strip() or "其他",
                    "note": str(row.get("note", "")).strip(),
                }
                assigned_sources.add(source)

        # 如果第二阶段没有返回某些 group，就用本地聚合候选做一次程序兜底。
        for source, grouped_item in self.grouped_stage_two_inputs.items():
            if source in assigned_sources:
                continue

            # 兜底时仍然沿用“同一个 source 只能归到一个表”的原则，
            # 只是不用 AI，而改用一个很轻量的启发式分数做归类。
            character_candidates = []
            term_candidates = []
            for candidate in grouped_item.get("candidates", []):
                if candidate.get("type") == "character":
                    character_candidates.append(candidate)
                elif candidate.get("type") == "term":
                    term_candidates.append(candidate)

            prefer_term = False
            if term_candidates and not character_candidates:
                prefer_term = True
            elif term_candidates and character_candidates:
                term_score = len(term_candidates) + sum(
                    1
                    for candidate in term_candidates
                    if str(candidate.get("category_path", "")).strip()
                    and str(candidate.get("category_path", "")).strip() != "其他"
                )
                character_score = len(character_candidates) + sum(
                    1
                    for candidate in character_candidates
                    if str(candidate.get("gender", "")).strip()
                    and str(candidate.get("gender", "")).strip() != "其他"
                )
                prefer_term = term_score > character_score

            if prefer_term:
                recommended_translation = ""
                category_path = "其他"
                notes = []
                for candidate in term_candidates + character_candidates:
                    translation = str(candidate.get("recommended_translation", "")).strip()
                    if not recommended_translation and translation:
                        recommended_translation = translation
                    category = str(candidate.get("category_path", "")).strip()
                    if category and category != "其他" and category_path == "其他":
                        category_path = category
                    note = str(candidate.get("note", "")).strip()
                    if note and note not in notes:
                        notes.append(note)

                merged_terms[source] = {
                    "source": source,
                    "recommended_translation": recommended_translation,
                    "category_path": category_path,
                    "note": " | ".join(notes),
                }
            else:
                recommended_translation = ""
                gender = "其他"
                notes = []
                for candidate in character_candidates + term_candidates:
                    translation = str(candidate.get("recommended_translation", "")).strip()
                    if not recommended_translation and translation:
                        recommended_translation = translation
                    candidate_gender = str(candidate.get("gender", "")).strip()
                    if candidate_gender and candidate_gender != "其他" and gender == "其他":
                        gender = candidate_gender
                    note = str(candidate.get("note", "")).strip()
                    if note and note not in notes:
                        notes.append(note)

                merged_characters[source] = {
                    "source": source,
                    "recommended_translation": recommended_translation,
                    "gender": gender,
                    "note": " | ".join(notes),
                }

        # 禁翻表不走第二阶段 AI，只做程序去重和常见标点过滤。
        # 原因是 non_translate 的目标更偏“去噪”和“合并重复 marker”，不需要角色/术语那种组内裁决。
        merged_non_translate = {}
        for result in first_stage_results:
            for row in result.get("non_translate", []):
                marker = str(row.get("marker", "")).strip()
                if not marker or all(
                    char.isspace() or char in self.COMMON_PUNCTUATION_CHARS
                    for char in marker
                ):
                    continue

                category = str(row.get("category", "")).strip()
                note = str(row.get("note", "")).strip()
                existing = merged_non_translate.get(marker)
                if existing is None:
                    merged_non_translate[marker] = {
                        "marker": marker,
                        "category": category,
                        "note": note,
                    }
                    continue

                if (
                    (not existing.get("category") or existing.get("category") == "其他")
                    and category
                    and category != "其他"
                ):
                    existing["category"] = category
                if not existing.get("note") and note:
                    existing["note"] = note

        return {
            "characters": list(merged_characters.values()),
            "terms": list(merged_terms.values()),
            "non_translate": list(merged_non_translate.values()),
        }

    # 从 AI 回复中提取 JSON 内容，兼容可能的多余文字或格式问题。
    def _parse_json_from_response(self, text: str) -> dict | None:
        # 兼容模型返回前后夹带说明文字的情况，只抽取最外层 JSON 对象。
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return None

    # 判断一个 source 是否完全包含另一个 source，且两者不完全相同。
    def _is_source_part_of(self, source: str, other_source: str) -> bool:
        source = str(source).strip()
        other_source = str(other_source).strip()
        if not source or not other_source or source == other_source:
            return False
        return other_source in source

    # 把第二阶段 AI 输出的 source 转换回第一阶段的最长 source，保证最终结果的统一性。
    def _canonicalize_group_source(self, source: str) -> str:
        source = str(source).strip()
        if not source:
            return ""
        return self.grouped_stage_two_source_aliases.get(source, source)

    # 计算一个 group 的 token 数，供第二阶段的批次切分参考。
    def _get_group_token_count(self, group: dict) -> int:
        group_json = json.dumps(group, ensure_ascii=False)
        return Tokener().num_tokens_from_str(group_json)
