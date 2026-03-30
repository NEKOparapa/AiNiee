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
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType


class AnalysisTask(ConfigMixin, LogMixin, Base):
    # 第一阶段按原文分块抽取候选；第二阶段按同一个 source 聚合后再让 AI 做合并判断。
    VERSION = 2
    CHUNK_TOKEN_LIMIT = 10000
    REDUCE_BATCH_GROUP_LIMIT = 40
    REDUCE_BATCH_CHAR_LIMIT = 18000
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

    def run(self) -> None:
        try:
            # 初始化分析任务，并复用翻译配置作为请求参数来源。
            Base.work_status = Base.STATUS.ANALYSIS_TASK
            self.emit(Base.EVENT.ANALYSIS_TASK_UPDATE, {"message": "正在初始化分析任务..."})

            self.config.initialize()
            self.config.prepare_for_translation(TaskType.TRANSLATION)
            self.request_limiter.set_limit(self.config.tpm_limit, self.config.rpm_limit)

            # 第一阶段输入仍然是按 token 切分的原文块。
            self.emit(Base.EVENT.ANALYSIS_TASK_UPDATE, {"message": "正在生成分析用文本片段..."})
            chunks = self.cache_manager.generate_analysis_source_chunks("token", self.CHUNK_TOKEN_LIMIT)

            # 第一阶段：并发抽取角色、术语、禁翻候选。
            self.emit(
                Base.EVENT.ANALYSIS_TASK_UPDATE,
                {"message": f"开始执行第一阶段分析任务，共 {len(chunks)} 个分块..."},
            )
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

                for future in concurrent.futures.as_completed(futures_stage1):
                    if Base.work_status == Base.STATUS.STOPING:
                        break
                    result = future.result()
                    if result:
                        first_stage_results.append(result)
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
            self.emit(
                Base.EVENT.ANALYSIS_TASK_UPDATE,
                {"message": f"开始执行第二阶段分析任务，共 {len(reduction_batches)} 个合并批次..."},
            )

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

                    for future in concurrent.futures.as_completed(futures_stage2):
                        if Base.work_status == Base.STATUS.STOPING:
                            break
                        result = future.result()
                        if result:
                            second_stage_results.append(result)
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
            self.emit(Base.EVENT.ANALYSIS_TASK_UPDATE, {"message": "正在整合最终分析结果..."})
            final_data = self._finalize_results(first_stage_results, second_stage_results)

            analysis_data = {
                "version": self.VERSION,
                "status": "success",
                "last_run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "characters": final_data.get("characters", []),
                "terms": final_data.get("terms", []),
                "non_translate": final_data.get("non_translate", []),
            }
            self.cache_manager.set_analysis_data(analysis_data)
            self.cache_manager.require_save_to_file(self.config.label_output_path)

            Base.work_status = Base.STATUS.IDLE
            self.emit(
                Base.EVENT.ANALYSIS_TASK_DONE,
                {"status": "success", "analysis_data": analysis_data, "message": "全文分析完成。"},
            )

        except Exception as error:
            self.error(f"分析任务执行失败: {error}", error if self.is_debug() else None)
            Base.work_status = Base.STATUS.IDLE
            self.emit(
                Base.EVENT.ANALYSIS_TASK_DONE,
                {"status": "error", "analysis_data": None, "message": str(error)},
            )

    def _run_first_stage(self, chunk: list) -> dict:
        try:
            # 第一阶段只负责尽量抽取候选，不做跨分块冲突判断。
            source_text = "\n".join(item.get("source_text", "") for item in chunk)
            system_prompt = (
                "你是一个游戏本地化与翻译辅助文本分析专家。请从以下文本中提取出【角色】、【术语】和【不翻译的词】。\n"
                "严格输出合法的JSON格式，包含'characters', 'terms', 'non_translate'三个数组。\n"
                "格式要求：\n"
                "{\n"
                "  \"characters\": [{\"source\": \"原文名字\", \"recommended_translation\": \"推荐译名\", \"gender\": \"性别(必须是: 男性、女性、其他 之一)\", \"note\": \"背景设定/备注\"}],\n"
                "  \"terms\": [{\"source\": \"原文术语\", \"recommended_translation\": \"推荐译名\", \"category_path\": \"分类(必须是: 身份、物品、组织、地名、其他 之一)\", \"note\": \"背景设定/备注\"}],\n"
                "  \"non_translate\": [{\"marker\": \"原文词或非文本\", \"category\": \"分类(必须是: 占位符、标记符、调用代码、转义控制符、变量键名、资源标识、数值公式、其他 之一)\", \"note\": \"原因/备注\"}]\n"
                "}"
            )
            requester = LLMRequester()
            _, _, response_content, _, _ = requester.sent_request(
                [{"role": "user", "content": source_text}],
                system_prompt,
                self.config.get_platform_configuration("translationReq"),
            )
            if response_content:
                return self._parse_json_from_response(response_content)
        except Exception as error:
            self.error(f"第一阶段提取失败: {error}")

        return {"characters": [], "terms": [], "non_translate": []}

    def _prepare_reduction_batches(self, first_stage_results: list) -> list:
        # 先把角色表、术语表按 source 聚成组。
        # 同一个词在多个分块里抽出的候选会被放进同一组，供第二阶段统一判断。
        grouped_inputs = {}

        for result in first_stage_results:
            for row in result.get("characters", []):
                source = str(row.get("source", "")).strip()
                if not source:
                    continue
                grouped_inputs.setdefault(source, {"source": source, "candidates": []})
                grouped_inputs[source]["candidates"].append(
                    {
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
                grouped_inputs.setdefault(source, {"source": source, "candidates": []})
                grouped_inputs[source]["candidates"].append(
                    {
                        "type": "term",
                        "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                        "gender": "",
                        "category_path": str(row.get("category_path", "")).strip(),
                        "note": str(row.get("note", "")).strip(),
                    }
                )

        self.grouped_stage_two_inputs = grouped_inputs

        # 候选越多越优先送去第二阶段，优先消解冲突最明显的词。
        grouped_items = list(grouped_inputs.values())
        grouped_items.sort(key=lambda item: (-len(item["candidates"]), item["source"]))

        batches = []
        current_batch = []
        current_chars = 0
        for item in grouped_items:
            item_chars = len(json.dumps(item, ensure_ascii=False))
            if current_batch and (
                len(current_batch) >= self.REDUCE_BATCH_GROUP_LIMIT
                or current_chars + item_chars > self.REDUCE_BATCH_CHAR_LIMIT
            ):
                batches.append(current_batch)
                current_batch = []
                current_chars = 0

            current_batch.append(item)
            current_chars += item_chars

        if current_batch:
            batches.append(current_batch)

        return batches

    def _run_second_stage(self, batch: list) -> dict:
        try:
            # 第二阶段输入是“同词候选组”，让 AI 在组内决定最终归类、译名、备注和分类。
            system_prompt = (
                "你是一个术语与角色合并专家。我会给你一批按 source 聚合后的候选数据。\n"
                "每个 group 里的 candidates 都是同一个原文词在不同分块里被提取出的候选结果，候选可能来自角色表或术语表。\n"
                "请你逐个 group 分析，最终每个 source 只能保留一条结果，并且只能出现在一个表里。\n"
                "如果判断它更适合作为角色，请输出到 characters；如果更适合作为术语，请输出到 terms。\n"
                "characters 字段必须包含 source, recommended_translation, gender, note。\n"
                "terms 字段必须包含 source, recommended_translation, category_path, note。\n"
                "其中 gender 只能是 男性/女性/其他；category_path 只能是 身份/物品/组织/地名/其他。\n"
                "重点是综合同一 source 下的所有候选，得出最优译名、最优备注，以及最合理的归类。\n"
                "严格只返回 JSON，不要解释，不要遗漏输入里的 group。"
            )
            requester = LLMRequester()
            _, _, response_content, _, _ = requester.sent_request(
                [{"role": "user", "content": json.dumps(batch, ensure_ascii=False)}],
                system_prompt,
                self.config.get_platform_configuration("translationReq"),
            )
            if response_content:
                parsed = self._parse_json_from_response(response_content)
                return {
                    "characters": list(parsed.get("characters", []) or []),
                    "terms": list(parsed.get("terms", []) or []),
                }
        except Exception as error:
            self.error(f"第二阶段合并失败: {error}")

        return {"characters": [], "terms": []}

    def _finalize_results(self, first_stage_results: list, second_stage_results: list) -> dict:
        # 先吸收第二阶段 AI 的正式结果，并保证同一个 source 只落到一个表里。
        merged_characters = {}
        merged_terms = {}
        assigned_sources = set()

        for result in second_stage_results:
            for row in result.get("characters", []):
                source = str(row.get("source", "")).strip()
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
                source = str(row.get("source", "")).strip()
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

    def _parse_json_from_response(self, text: str) -> dict:
        # 兼容模型返回前后夹带说明文字的情况，只抽取最外层 JSON 对象。
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return {"characters": [], "terms": [], "non_translate": []}
