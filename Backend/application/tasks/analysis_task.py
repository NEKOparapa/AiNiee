import concurrent.futures
import re
from datetime import datetime

import rapidjson as json

from Backend.application.execution_context import ExecutionContext
from Backend.domain.prompts.prompt_builder_extraction import PromptBuilderExtraction
from Backend.core.log import LogMixin
from Backend.infrastructure.llm.llm_requester import LLMRequester
from Backend.infrastructure.llm.request_limiter import RequestLimiter
from Backend.domain.config.task_config import TaskConfig
from Backend.infrastructure.tokenizers.tokener import Tokener
from Backend.domain import languages as TranslatorUtil


class AnalysisTask(LogMixin):
    """
    数据流概览 (总-分-分 结构)：
    [总] run(): 统筹调度整个分析任务。
    [分] 第一阶段 (Stage 1): 按 token 切分原文，独立请求 AI 抽取 candidates。
    [分] 第二阶段 (Stage 2): 按 source 聚合第一阶段的结果，交由 AI 裁决合并。
    [分] 最终阶段 (Finalize): 主线程收口结果，程序兜底遗漏项，清洗禁翻项并返回结果。
    """
    
    REDUCE_BATCH_TOKEN_LIMIT = 10000
    MAX_REQUEST_ATTEMPTS = 2
    COMMON_PUNCTUATION_CHARS = set(
        ".,!?;:'\"-_=+~`^…—、，。！？；：‘’“”()（）[]【】{}《》<>「」『』〈〉〔〕﹝﹞·•/\\|"
    )
    
    def __init__(self, cache_manager, set_active_executor=None, clear_active_executor=None, context=None) -> None:
        super().__init__()
        self.cache_manager = cache_manager
        self._set_active_executor = set_active_executor or (lambda executor: None)
        self._clear_active_executor = clear_active_executor or (lambda executor: None)
        self.context = context or ExecutionContext()
        self._operation_errors = []
        self._failed_requests = 0
        self.config = TaskConfig()
        self.request_limiter = RequestLimiter()
        self.grouped_stage_two_inputs = {} # 第二阶段的输入结构：{主source: {source, merged_sources, candidates}}
        self.grouped_stage_two_source_aliases = {} # 第二阶段的 source 别名映射：{所有source: 主source}


    # ========================================================================
    # 1. 总流程控制 (总)
    # ========================================================================

    def run(self) -> dict:
        """Return the complete or partial analysis; persistence belongs to the caller."""
        first_stage_results, second_stage_results = [], []
        self._operation_errors = []
        self._failed_requests = 0
        self.grouped_stage_two_inputs = {}
        self.grouped_stage_two_source_aliases = {}
        prepared = False
        try:
            self._report_progress_update("prepare", "准备中", 0, 0, "正在初始化分析任务...", "加载配置。")
            if not self.context.is_cancelled():
                self.config = TaskConfig.from_snapshot(TaskConfig.read_snapshot(), interface_role="extract")
                self.request_limiter.set_limit(self.config.rpm_limit)
                token_limit = max(1, int(getattr(self.config, "extract_task_token_limit", 10000)))
                chunks = self.cache_manager.generate_analysis_source_chunks("token", token_limit)
                self._run_stage(chunks, self._run_first_stage, "stage1", "第一阶段", first_stage_results)
                # Even on cancellation, group completed extraction results for the local fallback.
                reduction_batches = self._prepare_reduction_batches(first_stage_results)
                prepared = True
                if not self.context.is_cancelled():
                    self._run_stage(reduction_batches, self._run_second_stage, "stage2", "第二阶段", second_stage_results)
        except Exception as error:
            self._operation_errors.append(str(error))
            self.context.cancel()
            self.error(f"分析任务执行失败: {error}", error)

        analysis_data = None
        try:
            if first_stage_results or second_stage_results or (not self.context.is_cancelled() and not self._operation_errors and not self._failed_requests):
                if not prepared:
                    self._prepare_reduction_batches(first_stage_results)
                self._report_progress_update("finalize", "结果整合", 0, 1, "正在整合分析结果...", "执行本地兜底与禁翻清洗。")
                final_data = self._finalize_results(first_stage_results, second_stage_results)
                if not getattr(self.config, "auto_extract_non_translate_switch", False):
                    final_data["non_translate"] = []
                analysis_data = {
                    "last_run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "characters": final_data.get("characters", []),
                    "terms": final_data.get("terms", []),
                    "non_translate": final_data.get("non_translate", []),
                }
                analysis_data["stats"] = {
                    "character_count": len(analysis_data["characters"]),
                    "term_count": len(analysis_data["terms"]),
                    "non_translate_count": len(analysis_data["non_translate"]),
                }
                analysis_data["stats"]["total_hits"] = sum(analysis_data["stats"].values())
                self._report_progress_update("finalize", "结果整合", 1, 1, "分析结果已生成。", "")
        except Exception as error:
            self._operation_errors.append(str(error))
            self.error(f"分析结果整合失败: {error}", error)
        if self._operation_errors:
            status = "partial" if analysis_data else "error"
        elif self.context.is_cancelled():
            status = "cancelled"
        elif self._failed_requests:
            status = "partial" if first_stage_results or second_stage_results else "error"
        else:
            status = "success"
        if analysis_data is not None:
            analysis_data["status"] = status
        return {
            "status": status, "analysis_data": analysis_data,
            "message": "; ".join(self._operation_errors) or (
                "分析任务已停止。" if status == "cancelled" else
                "部分分析请求失败。" if self._failed_requests else "全文分析完成。"
            ),
            "operation_errors": list(self._operation_errors), "failed_requests": self._failed_requests,
        }

    def _run_stage(self, chunks, worker, phase, phase_label, results):
        """Bound queued requests and collect every in-flight result before releasing the task."""
        executor = None
        futures, handled = set(), set()
        processed = 0

        def collect(future):
            nonlocal processed
            if future in handled or future.cancelled():
                return
            handled.add(future)
            processed += 1
            try:
                result = future.result()
            except Exception as error:
                self.error(f"{phase_label}请求失败: {error}")
                result = None
            if result is not None:
                results.append(result)
            elif not self.context.is_cancelled():
                self._failed_requests += 1
            self._report_progress_update(phase, phase_label, processed, len(chunks),
                                         f"{phase_label}处理中...", f"已完成 {processed} / {len(chunks)} 个分块。")

        self._report_progress_update(phase, phase_label, 0, len(chunks), f"开始{phase_label}...", "")
        try:
            if not chunks or self.context.is_cancelled():
                return
            workers = max(1, int(self.config.actual_thread_counts))
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"analysis_{phase}")
            self._set_active_executor(executor)
            next_index, pending = 0, set()
            while pending or (next_index < len(chunks) and not self.context.is_cancelled()):
                while next_index < len(chunks) and len(pending) < workers and not self.context.is_cancelled():
                    future = executor.submit(worker, chunks[next_index])
                    pending.add(future)
                    futures.add(future)
                    next_index += 1
                if not pending:
                    break
                done, pending = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    collect(future)
        except Exception:
            self.context.cancel()
            raise
        finally:
            if executor:
                try:
                    executor.shutdown(wait=True, cancel_futures=self.context.is_cancelled())
                    for future in futures:
                        collect(future)
                finally:
                    self._clear_active_executor(executor)

    # ========================================================================
    # 2. 第一阶段：独立文本提取 (分)
    # ========================================================================

    def _run_first_stage(self, chunk: list) -> dict | None:
        """执行单分块的角色/术语/禁翻提取"""
        try:
            # 将 chunk 中的 source_text 合并为一个字符串
            source_text = "\n".join(item.get("source_text", "") for item in chunk)

            # 构建该chunk的系统提示和消息列表
            system_prompt, messages = self._build_first_stage_prompt(source_text)
            
            # 执行请求并返回结果，失败与成功的空提取结果分开统计
            result = self._execute_analysis_request(
                stage_label="第一阶段提取",
                system_prompt=system_prompt,
                messages=messages,
                required_fields=("characters", "terms", "non_translate")
            )
            return result
            
        except Exception as error:
            self.error(f"第一阶段提取失败: {error}")
            return None

    def _get_recommended_translation_language_requirement(self) -> str:
        """构建 recommended_translation 的目标语言约束说明。"""
        target_language = str(getattr(self.config, "target_language", "") or "").strip()
        display_name = TranslatorUtil.pair.get(target_language, "")
        if display_name:
            return f"角色与术语的译名/分类/备注，不翻译项的分类/备注都必须写成{display_name}。"

        return "角色与术语的译名/分类/备注，不翻译项的分类/备注都必须跟随当前译文语言设置。"

    def _build_first_stage_prompt(self, source_text: str) -> tuple[str, list[dict]]:
            """第一阶段：独立文本提取（优化版提示词）"""
            system_prompt = PromptBuilderExtraction.build_system(self.config, PromptBuilderExtraction.BASIC)
            
            # 优化 Few-Shot：包含更丰富的混合场景，注意 {{}} 是转义 Python 的 f-string 占位符
            fake_user = (
                "请分析以下文本并提取信息，角色与术语的译名/分类/备注，不翻译项的分类/备注都必须写成简体中文。\n"
                "---\n"
                "露娜小姐：请携带[圣剑]前往星门集合。\n"
                "精灵族战士即将施放月光斩。\n"
                "系统提示：欢迎回来，{{player_name}}！<br>请注意<color=red>HP</color>的变化。\n"
                "---\n"
                "请输出 JSON 提取结果。"
            )
            fake_assistant = (
                "```json\n"
                "{\n"
                "  \"characters\": [\n"
                "    {\"source\": \"露娜小姐\", \"recommended_translation\": \"露娜小姐\", \"gender\": \"女性\", \"note\": \"NPC称呼\"}\n"
                "  ],\n"
                "  \"terms\": [\n"
                "    {\"source\": \"圣剑\", \"recommended_translation\": \"圣剑\", \"category_path\": \"物品\", \"note\": \"武器名称\"},\n"
                "    {\"source\": \"星门\", \"recommended_translation\": \"星门\", \"category_path\": \"地名\", \"note\": \"地点\"},\n"
                "    {\"source\": \"月光斩\", \"recommended_translation\": \"月光斩\", \"category_path\": \"技能\", \"note\": \"招式名称\"},\n"
                "    {\"source\": \"精灵族\", \"recommended_translation\": \"精灵族\", \"category_path\": \"种族\", \"note\": \"种族名称\"}\n"
                "  ],\n"
                "  \"non_translate\": [\n"
                "    {\"marker\": \"{{player_name}}\", \"category\": \"变量\", \"note\": \"玩家名变量\"},\n"
                "    {\"marker\": \"<br>\", \"category\": \"标签\", \"note\": \"换行符\"},\n"
                "    {\"marker\": \"<color=red>\", \"category\": \"标签\", \"note\": \"颜色富文本标签\"},\n"
                "    {\"marker\": \"</color>\", \"category\": \"标签\", \"note\": \"颜色富文本标签闭合\"}\n"
                "  ]\n"
                "}\n"
                "```"
            )
            
            language_requirement = self._get_recommended_translation_language_requirement()
            user_prompt = (
                f"请分析以下文本并提取信息，{language_requirement}\n"
                f"---\n{source_text}\n---\n"
                "请输出 JSON 提取结果。"
            )
            messages = [
                {"role": "user", "content": fake_user},
                {"role": "assistant", "content": fake_assistant},
                {"role": "user", "content": user_prompt},
            ]
            return system_prompt, messages


    # ========================================================================
    # 3. 第二阶段：候选归并与 AI 裁决 (分)
    # ========================================================================

    def _run_second_stage(self, batch: list) -> dict | None:
        """对聚合后的长短变体候选组，让 AI 裁决去留和分类"""
        try:
            system_prompt, messages = self._build_second_stage_prompt(batch)
            
            # 第二阶段特有业务校验：输入 batch 不为空时，输出不能全为空
            def stage_two_validator(parsed: dict):
                if batch and not parsed.get("characters") and not parsed.get("terms"):
                    return False, "未返回任何合并裁决结果"
                return True, ""

            # 复用通用流水线，注入第二阶段专属校验规则
            result = self._execute_analysis_request(
                stage_label="第二阶段合并",
                system_prompt=system_prompt,
                messages=messages,
                required_fields=("characters", "terms"),
                custom_validator=stage_two_validator
            )
            return result
            
        except Exception as error:
            self.error(f"第二阶段合并失败: {error}")
            return None

    def _prepare_reduction_batches(self, first_stage_results: list) -> list:
        """组装第二阶段所需的候选组批次：短词挂靠长词"""
        raw_grouped_inputs = {}
        for result in first_stage_results:
            for row in result.get("characters", []):
                source = str(row.get("source", "")).strip()
                if not source: continue
                raw_grouped_inputs.setdefault(source, {"source": source, "merged_sources": [source], "candidates": []})
                raw_grouped_inputs[source]["candidates"].append({
                    "candidate_source": source, "type": "character", "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                    "gender": str(row.get("gender", "")).strip(), "category_path": "", "note": str(row.get("note", "")).strip(),
                })
            for row in result.get("terms", []):
                source = str(row.get("source", "")).strip()
                if not source: continue
                raw_grouped_inputs.setdefault(source, {"source": source, "merged_sources": [source], "candidates": []})
                raw_grouped_inputs[source]["candidates"].append({
                    "candidate_source": source, "type": "term", "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                    "gender": "", "category_path": str(row.get("category_path", "")).strip(), "note": str(row.get("note", "")).strip(),
                })

        enable_short_name_merge = bool(
            getattr(self.config, "extract_short_name_merge_switch", True)
        )

        if not enable_short_name_merge:
            grouped_inputs = {
                source: {
                    "source": source,
                    "merged_sources": [source],
                    "candidates": list(grouped_item.get("candidates", [])),
                }
                for source, grouped_item in raw_grouped_inputs.items()
            }
            source_aliases = {source: source for source in grouped_inputs}
        else:
            sorted_sources = sorted(raw_grouped_inputs.keys(), key=lambda s: (-len(s), s))
            grouped_inputs, source_aliases, consumed_sources = {}, {}, set()

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
                    if other_source in consumed_sources or other_source == source:
                        continue
                    if other_source in source:  # 短 source 挂靠
                        merged_group["merged_sources"].append(other_source)
                        merged_group["candidates"].extend(
                            raw_grouped_inputs[other_source].get("candidates", [])
                        )
                        source_aliases[other_source] = source
                        consumed_sources.add(other_source)

        self.grouped_stage_two_inputs = grouped_inputs
        self.grouped_stage_two_source_aliases = source_aliases

        grouped_items = sorted(list(grouped_inputs.values()), key=lambda item: (-len(item["source"]), -len(item["candidates"])))
        batches, current_batch, current_tokens = [], [], 0
        for item in grouped_items:
            item_tokens = Tokener().num_tokens_from_str(json.dumps(item, ensure_ascii=False))
            if current_batch and (current_tokens + item_tokens > self.REDUCE_BATCH_TOKEN_LIMIT):
                batches.append(current_batch)
                current_batch, current_tokens = [], 0
            current_batch.append(item)
            current_tokens += item_tokens
        if current_batch: batches.append(current_batch)

        return batches

    def _build_second_stage_prompt(self, batch: list) -> tuple[str, list[dict]]:
        """第二阶段：候选归并与 AI 裁决（优化版提示词）"""
        system_prompt = PromptBuilderExtraction.build_system(self.config, PromptBuilderExtraction.JUDGMENT)
        
        # 优化 Few-Shot：展示如何解决类型冲突和合并备注
        sample_group = [
            {
                "source": "亚瑟王",
                "merged_sources": ["亚瑟王", "亚瑟"],
                "candidates": [
                    {"type": "character", "recommended_translation": "King Arthur", "gender": "男性", "note": "历史人物"},
                    {"type": "term", "recommended_translation": "Arthur", "category_path": "称号", "note": "错误分类为术语"}
                ]
            },
            {
                "source": "月光斩",
                "merged_sources": ["月光斩"],
                "candidates": [
                    {"type": "term", "recommended_translation": "Moon Slash", "category_path": "技能", "note": "剑技名称"}
                ]
            },
            {
                "source": "精灵族",
                "merged_sources": ["精灵族"],
                "candidates": [
                    {"type": "term", "recommended_translation": "Elves", "category_path": "种族", "note": "种族名称"}
                ]
            }
        ]
        import rapidjson as json
        
        fake_user = (
            "请分析以下候选组并完成合并裁决，`recommended_translation` 必须写成简体中文。\n"
            f"---\n{json.dumps(sample_group, ensure_ascii=False)}\n---\n"
            "请输出 JSON 合并结果。"
        )
        fake_assistant = (
            "```json\n"
            "{\n"
            "  \"characters\": [\n"
            "    {\"source\": \"亚瑟王\", \"recommended_translation\": \"King Arthur\", \"gender\": \"男性\", \"note\": \"历史人物\"}\n"
            "  ],\n"
            "  \"terms\": [\n"
            "    {\"source\": \"月光斩\", \"recommended_translation\": \"Moon Slash\", \"category_path\": \"技能\", \"note\": \"剑技名称\"},\n"
            "    {\"source\": \"精灵族\", \"recommended_translation\": \"Elves\", \"category_path\": \"种族\", \"note\": \"种族名称\"}\n"
            "  ]\n"
            "}\n"
            "```"
        )
        language_requirement = self._get_recommended_translation_language_requirement()
        user_prompt = (
            f"请分析以下候选组并完成合并裁决，{language_requirement}\n"
            f"---\n{json.dumps(batch, ensure_ascii=False)}\n---\n"
            "请输出 JSON 合并结果。"
        )
        
        messages = [
            {"role": "user", "content": fake_user},
            {"role": "assistant", "content": fake_assistant},
            {"role": "user", "content": user_prompt},
        ]
        return system_prompt, messages


    # ========================================================================
    # 4. 最终阶段：整合兜底与落盘 (分)
    # ========================================================================

    def _get_candidate_occurrence_count(self, source: str, candidate_type: str) -> int:
        source = str(source or "").strip()
        candidate_type = str(candidate_type or "").strip()
        grouped_item = self.grouped_stage_two_inputs.get(source) or {}
        occurrence_count = sum(
            1
            for candidate in grouped_item.get("candidates", []) or []
            if candidate.get("type") == candidate_type
            and str(candidate.get("candidate_source", "")).strip() == source
        )
        return max(1, occurrence_count)

    def _finalize_results(self, first_stage_results: list, second_stage_results: list) -> dict:
        """主线程收口：采纳 AI 裁决结果 -> 启发式兜底缺失项 -> 清洗禁翻项"""
        merged_characters, merged_terms, assigned_sources = {}, {}, set()

        # 1. 吸收并规范化第二阶段 AI 的结果
        for result in second_stage_results:
            for row in result.get("characters", []):
                source = str(row.get("source", "")).strip()
                source = self.grouped_stage_two_source_aliases.get(source, source)
                if not source or source in assigned_sources: continue
                merged_characters[source] = {
                    "source": source, "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                    "gender": str(row.get("gender", "")).strip() or "其他", "note": str(row.get("note", "")).strip(),
                    "occurrence_count": self._get_candidate_occurrence_count(source, "character"),
                }
                assigned_sources.add(source)

            for row in result.get("terms", []):
                source = str(row.get("source", "")).strip()
                source = self.grouped_stage_two_source_aliases.get(source, source)
                if not source or source in assigned_sources: continue
                merged_terms[source] = {
                    "source": source, "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                    "category_path": str(row.get("category_path", "")).strip() or "其他", "note": str(row.get("note", "")).strip(),
                    "occurrence_count": self._get_candidate_occurrence_count(source, "term"),
                }
                assigned_sources.add(source)

        # 2. 对 AI 丢弃的组进行启发式程序兜底
        for source, grouped_item in self.grouped_stage_two_inputs.items():
            if source in assigned_sources: continue

            c_cands = [c for c in grouped_item.get("candidates", []) if c.get("type") == "character"]
            t_cands = [c for c in grouped_item.get("candidates", []) if c.get("type") == "term"]
            
            prefer_term = False
            if t_cands and not c_cands: prefer_term = True
            elif t_cands and c_cands:
                t_score = len(t_cands) + sum(1 for c in t_cands if str(c.get("category_path", "")).strip() not in ["", "其他"])
                c_score = len(c_cands) + sum(1 for c in c_cands if str(c.get("gender", "")).strip() not in ["", "其他"])
                prefer_term = t_score > c_score

            notes = []
            all_cands = t_cands + c_cands if prefer_term else c_cands + t_cands
            trans = next((str(c.get("recommended_translation", "")).strip() for c in all_cands if str(c.get("recommended_translation", "")).strip()), "")
            
            for c in all_cands:
                if n := str(c.get("note", "")).strip():
                    if n not in notes: notes.append(n)

            if prefer_term:
                cat = next((str(c.get("category_path", "")).strip() for c in all_cands if str(c.get("category_path", "")).strip() not in ["", "其他"]), "其他")
                merged_terms[source] = {
                    "source": source, "recommended_translation": trans, "category_path": cat, "note": " | ".join(notes),
                    "occurrence_count": self._get_candidate_occurrence_count(source, "term"),
                }
            else:
                gen = next((str(c.get("gender", "")).strip() for c in all_cands if str(c.get("gender", "")).strip() not in ["", "其他"]), "其他")
                merged_characters[source] = {
                    "source": source, "recommended_translation": trans, "gender": gen, "note": " | ".join(notes),
                    "occurrence_count": self._get_candidate_occurrence_count(source, "character"),
                }

        # 3. 第一阶段禁翻项的清洗合并 (不走第二阶段 AI)
        merged_non_translate = {}
        for result in first_stage_results:
            for row in result.get("non_translate", []):
                marker = str(row.get("marker", "")).strip()
                if not marker or all(char.isspace() or char in self.COMMON_PUNCTUATION_CHARS for char in marker):
                    continue

                cat, note = str(row.get("category", "")).strip(), str(row.get("note", "")).strip()
                existing = merged_non_translate.setdefault(
                    marker,
                    {"marker": marker, "category": cat, "note": note, "occurrence_count": 0},
                )
                existing["occurrence_count"] = int(existing.get("occurrence_count", 0) or 0) + 1
                
                if (not existing["category"] or existing["category"] == "其他") and cat and cat != "其他": existing["category"] = cat
                if not existing["note"] and note: existing["note"] = note

        return {
            "characters": list(merged_characters.values()),
            "terms": list(merged_terms.values()),
            "non_translate": list(merged_non_translate.values()),
        }


    # ========================================================================
    # 通用工具
    # ========================================================================

    def _calculate_progress_percent(self, phase: str, current: int = 0, total: int = 0) -> int:
        """根据阶段和进度计算总体百分比"""
        current, total = max(0, int(current or 0)), max(0, int(total or 0))
        if phase == "prepare": return 0
        if phase == "stage1": return 10 + int((current / total) * 50) if total > 0 else 60
        if phase == "stage2": return 60 + int((current / total) * 30) if total > 0 else 90
        if phase == "finalize": return 90 + int((current / total) * 10) if total > 0 else 90
        return 0

    def _report_progress_update(self, phase: str, phase_label: str, current: int, total: int, message: str, detail: str) -> None:
        if self._operation_errors or not self.context.on_progress:
            return
        try:
            self.context.on_progress({
                "status": "running", "phase": phase, "phase_label": phase_label,
                "current": max(0, int(current or 0)), "total": max(0, int(total or 0)),
                "percent": self._calculate_progress_percent(phase, current, total),
                "message": message, "detail": detail,
            })
        except Exception as error:
            self._operation_errors.append(str(error))
            self.context.cancel()

    # ---------------------------------------------------------
    # ★ 完整的请求发送与回复检查器 (一、二阶段共用流水线)
    # ---------------------------------------------------------
    
    def _execute_analysis_request(
        self, 
        stage_label: str, 
        system_prompt: str, 
        messages: list[dict], 
        required_fields: tuple[str, ...], 
        custom_validator=None
    ) -> dict | None:
        """
        大模型请求的统一流水线：
        请求发送 -> 异常捕获 -> JSON 提取 -> 基础字段校验 -> 自定义业务校验 -> 数据清洗 -> 失败重试
        """
        last_error = "未知错误"

        for attempt in range(1, self.MAX_REQUEST_ATTEMPTS + 1):
            if self.context.is_cancelled():
                return None

            try:
                # 1. 发送请求
                requester = LLMRequester()
                platform_config = self.config.get_active_platform_configuration()
                platform_config["is_cancelled"] = self.context.is_cancelled
                skip, _, response_content, _, _ = requester.sent_request(
                    [dict(msg) for msg in messages],
                    system_prompt,
                    platform_config,
                )

                if skip:
                    if self.context.is_cancelled(): return None
                    last_error = "请求被跳过或接口返回错误"
                    continue

                response_content = str(response_content or "").strip()
                if not response_content:
                    last_error = "模型回复为空"
                    continue

                # 2. 从回复中提取 JSON (兼容多余文字)
                parsed_json = self._extract_json_from_text(response_content)
                if not parsed_json:
                    last_error = "未匹配到合法的 JSON 结构"
                    continue

                # 3. 基础结构校验 (确保必须字段存在且为列表)
                is_valid, validation_error = self._validate_base_structure(parsed_json, required_fields)
                if not is_valid:
                    last_error = validation_error
                    continue

                # 4. 阶段自定义业务校验 (如需要)
                if custom_validator:
                    is_valid, validation_error = custom_validator(parsed_json)
                    if not is_valid:
                        last_error = validation_error
                        continue

                # 5. 成功：归一化并清洗无用字段，安全返回
                return {field: list(parsed_json.get(field) or []) for field in required_fields}

            except Exception as error:
                if self.context.is_cancelled(): return None
                last_error = str(error)

            # 记录重试日志
            if attempt < self.MAX_REQUEST_ATTEMPTS:
                self.warning(f"{stage_label} 第 {attempt} 次尝试失败，将重试一次：{last_error}")
            else:
                self.error(f"{stage_label} 第 {attempt} 次尝试失败：{last_error}")

        return None

    def _extract_json_from_text(self, text: str) -> dict | None:
        """辅助方法：正则提取被包裹的 JSON"""
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict): return parsed
            except json.JSONDecodeError:
                pass
        return None

    def _validate_base_structure(self, parsed: dict, required_fields: tuple[str, ...]) -> tuple[bool, str]:
        """辅助方法：校验基础结构"""
        for field in required_fields:
            if field not in parsed: return False, f"缺少必须字段: {field}"
            if not isinstance(parsed.get(field), list): return False, f"字段 {field} 必须是数组"
        return True, ""
