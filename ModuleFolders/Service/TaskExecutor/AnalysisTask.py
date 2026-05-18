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
from ModuleFolders.Service.TaskExecutor import TranslatorUtil


class AnalysisTask(ConfigMixin, LogMixin, Base):
    """
    数据流概览 (总-分-分 结构)：
    [总] run(): 统筹调度整个分析任务。
    [分] 第一阶段 (Stage 1): 按 token 切分原文，独立请求 AI 抽取 candidates。
    [分] 第二阶段 (Stage 2): 按 source 聚合第一阶段的结果，交由 AI 裁决合并。
    [分] 最终阶段 (Finalize): 主线程收口结果，程序兜底遗漏项，清洗禁翻项并落盘。
    """
    
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
        self.grouped_stage_two_inputs = {} # 第二阶段的输入结构：{主source: {source, merged_sources, candidates}}
        self.grouped_stage_two_source_aliases = {} # 第二阶段的 source 别名映射：{所有source: 主source}


    # ========================================================================
    # 1. 总流程控制 (总)
    # ========================================================================

    def run(self) -> None:
        """主入口统筹：准备 -> 第一阶段并发 -> 第二阶段聚合与并发 -> 最终兜底合并 -> 落盘"""
        try:
            # --- [准备阶段] ---
            Base.work_status = Base.STATUS.ANALYSIS_TASK
            self.info("开始执行文本分析任务 ...")
            self._emit_progress_update(
                "prepare",
                self.tra("准备中"),
                0,
                0,
                self.tra("正在初始化分析任务..."),
                self.tra("加载配置与限流设置。"),
            )
            self.config.initialize("extract")
            self.config.prepare_for_active_platform("extract")
            self.request_limiter.set_limit(self.config.rpm_limit)
            self.info(
                "分析配置: 模型 - {0}, 并发线程 - {1}, RPM - {2}".format(
                    self.config.model,
                    self.config.actual_thread_counts,
                    self.config.rpm_limit,
                )
            )

            # 生成分析用文本片段：按 token 切分，确保每个分块都在模型处理能力范围内，同时保持文本的完整性和上下文连贯。
            self._emit_progress_update(
                "prepare",
                self.tra("准备中"),
                0,
                0,
                self.tra("正在生成分析用文本片段..."),
                self.tra("按 token 切分项目原文。"),
            )
            chunks = self.cache_manager.generate_analysis_source_chunks("token", self.CHUNK_TOKEN_LIMIT)
            self.info(f"分析文本切分完成，共生成 {len(chunks)} 个分块。")

            # --- [第一阶段] ---
            self._emit_progress_update(
                "stage1",
                self.tra("第一阶段"),
                0,
                len(chunks),
                self.tra("开始执行第一阶段分析任务..."),
                self.tra("共 {0} 个分块。").format(len(chunks)),
            )
            self.info(f"开始执行第一阶段提取，共 {len(chunks)} 个分块。")
            first_stage_results = []
            executor_stage1 = concurrent.futures.ThreadPoolExecutor(max_workers=self.config.actual_thread_counts, thread_name_prefix="analysis_stage1")
            self._set_active_executor(executor_stage1)
            try:
                futures_stage1 = [executor_stage1.submit(self._run_first_stage, chunk) for chunk in chunks]
                for i, future in enumerate(concurrent.futures.as_completed(futures_stage1), 1):
                    if Base.work_status == Base.STATUS.STOPING: break
                    if result := future.result(): first_stage_results.append(result)
                    self._emit_progress_update(
                        "stage1",
                        self.tra("第一阶段"),
                        i,
                        len(chunks),
                        self.tra("第一阶段提取中..."),
                        self.tra("已完成 {0} / {1} 个分块。").format(i, len(chunks)),
                    )
            finally:
                executor_stage1.shutdown(wait=True, cancel_futures=Base.work_status == Base.STATUS.STOPING)
                self._clear_active_executor(executor_stage1)

            if Base.work_status == Base.STATUS.STOPING: return self._handle_stop()
            self.info(f"第一阶段提取完成，成功收集 {len(first_stage_results)} 个分块结果。")

            # --- [第二阶段] ---
            reduction_batches = self._prepare_reduction_batches(first_stage_results) # 准备第二阶段的批次：将第一阶段的结果按 source 聚合，短词挂靠长词，形成待裁决的候选组。
            self._emit_progress_update(
                "stage2",
                self.tra("第二阶段"),
                0,
                len(reduction_batches),
                self.tra("开始执行第二阶段分析任务..."),
                self.tra("共 {0} 个合并批次。").format(len(reduction_batches)),
            )
            self.info(f"开始执行第二阶段合并，共 {len(reduction_batches)} 个批次。")
            second_stage_results = []
            if reduction_batches:
                executor_stage2 = concurrent.futures.ThreadPoolExecutor(max_workers=self.config.actual_thread_counts, thread_name_prefix="analysis_stage2")
                self._set_active_executor(executor_stage2)
                try:
                    futures_stage2 = [executor_stage2.submit(self._run_second_stage, batch) for batch in reduction_batches]
                    for i, future in enumerate(concurrent.futures.as_completed(futures_stage2), 1):
                        if Base.work_status == Base.STATUS.STOPING: break
                        if result := future.result(): second_stage_results.append(result)
                        self._emit_progress_update(
                            "stage2",
                            self.tra("第二阶段"),
                            i,
                            len(reduction_batches),
                            self.tra("第二阶段合并中..."),
                            self.tra("已完成 {0} / {1} 个合并批次。").format(i, len(reduction_batches)),
                        )
                finally:
                    executor_stage2.shutdown(wait=True, cancel_futures=Base.work_status == Base.STATUS.STOPING)
                    self._clear_active_executor(executor_stage2)
                self.info(f"第二阶段合并完成，成功收集 {len(second_stage_results)} 个批次结果。")
            else:
                self.info("第二阶段没有可合并候选，已跳过 AI 裁决。")

            if Base.work_status == Base.STATUS.STOPING: return self._handle_stop()

            # --- [最终阶段] ---
            self._emit_progress_update(
                "finalize",
                self.tra("结果整合"),
                0,
                1,
                self.tra("正在整合最终分析结果..."),
                self.tra("执行本地兜底与禁翻清洗。"),
            )
            self.info("开始汇总最终分析结果并写回缓存 ...")
            final_data = self._finalize_results(first_stage_results, second_stage_results)
            self._emit_progress_update(
                "finalize",
                self.tra("结果整合"),
                1,
                1,
                self.tra("分析结果已生成..."),
                self.tra("正在写回项目缓存。"),
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
                },
            }
            analysis_data["stats"]["total_hits"] = sum(analysis_data["stats"].values())
            
            self.cache_manager.set_analysis_data(analysis_data)
            self.cache_manager.require_save_to_file()
            self.info(
                "文本分析完成。角色 {0} 个，术语 {1} 个，非翻译项 {2} 个，总计 {3} 个。".format(
                    analysis_data["stats"]["character_count"],
                    analysis_data["stats"]["term_count"],
                    analysis_data["stats"]["non_translate_count"],
                    analysis_data["stats"]["total_hits"],
                )
            )
            Base.work_status = Base.STATUS.IDLE
            self.emit(
                Base.EVENT.ANALYSIS_TASK_DONE,
                {
                    "status": "success",
                    "analysis_data": analysis_data,
                    "message": self.tra("全文分析完成。"),
                },
            )

        except Exception as error:
            self.error(f"分析任务执行失败: {error}", error)
            Base.work_status = Base.STATUS.IDLE
            self.emit(Base.EVENT.ANALYSIS_TASK_DONE, {"status": "error", "analysis_data": None, "message": str(error)})

    def _handle_stop(self) -> None:
        Base.work_status = Base.STATUS.TASKSTOPPED
        self.info("文本分析任务已停止。")
        self.emit(
            Base.EVENT.ANALYSIS_TASK_DONE,
            {
                "status": "stopped",
                "analysis_data": None,
                "message": self.tra("分析任务已停止。"),
            },
        )


    # ========================================================================
    # 2. 第一阶段：独立文本提取 (分)
    # ========================================================================

    def _run_first_stage(self, chunk: list) -> dict:
        """执行单分块的角色/术语/禁翻提取"""
        try:
            # 将 chunk 中的 source_text 合并为一个字符串
            source_text = "\n".join(item.get("source_text", "") for item in chunk)

            # 构建该chunk的系统提示和消息列表
            system_prompt, messages = self._build_first_stage_prompt(source_text)
            
            # 执行请求并返回结果，若失败则返回空结构
            result = self._execute_analysis_request(
                stage_label="第一阶段提取",
                system_prompt=system_prompt,
                messages=messages,
                required_fields=("characters", "terms", "non_translate")
            )
            return result or {"characters": [], "terms": [], "non_translate": []}
            
        except Exception as error:
            self.error(f"第一阶段提取失败: {error}")
            return {"characters": [], "terms": [], "non_translate": []}

    def _get_recommended_translation_language_requirement(self) -> str:
        """构建 recommended_translation 的目标语言约束说明。"""
        target_language = str(getattr(self.config, "target_language", "") or "").strip()
        display_name = TranslatorUtil.pair.get(target_language, "")
        if display_name:
            return f"角色与术语的译名/分类/备注，不翻译项的分类/备注都必须写成{display_name}。"

        return "角色与术语的译名/分类/备注，不翻译项的分类/备注都必须跟随当前译文语言设置。"

    def _build_first_stage_prompt(self, source_text: str) -> tuple[str, list[dict]]:
            """第一阶段：独立文本提取（优化版提示词）"""
            system_prompt = (
                "你是一个专业的游戏与本地化文本分析专家。你的唯一任务是从给定的文本中提取出：角色名、专有名词（术语）以及不需要翻译的代码/标记。\n"
                "【严格执行以下规则】\n"
                "1. 原样提取：提取的 `source` 必须与原文一字不差，绝对不要修改大小写或标点。\n"
                "2. 拒绝脑补：只提取文本中实际出现的实体，不要联想或创造。\n"
                "3. 宁缺毋滥：对于普通词汇（如“苹果”、“跑”、“明天”），不要提取。如果没有值得提取的内容，返回空列表。\n"
                "4. 分类规范：\n"
                "   - characters(角色): 文本中出现的具体人物、怪物、神明等名字。gender 建议分类: 男性/女性/其他。\n"
                "   - terms(术语): 身份称谓、地名、组织、物品名、技能名、种族名、独特概念等。category_path 建议分类: 身份/物品/组织/地名/技能/种族/其他。\n"
                "   - non_translate(不翻译项): 必须保留的机器代码，如 HTML标签(<b>)、占位符(%s)、变量({{name}})。category 建议分类: 标签/变量/占位符/标记符/转义控制符/资源标识/数值公式/其他。\n"
                "【输出格式】\n"
                "必须输出合法的 JSON 代码块，严格遵守以下结构：\n"
                "```json\n"
                "{\n"
                "  \"characters\": [{\"source\": \"原文\", \"recommended_translation\": \"推荐译名\", \"gender\": \"\", \"note\": \"\"}],\n"
                "  \"terms\": [{\"source\": \"原文\", \"recommended_translation\": \"推荐译名\", \"category_path\": \"\", \"note\": \"\"}],\n"
                "  \"non_translate\": [{\"marker\": \"代码或标记\", \"category\": \"\", \"note\": \"\"}]\n"
                "}\n"
                "```"
            )
            
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

    def _run_second_stage(self, batch: list) -> dict:
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
            return result or {"characters": [], "terms": []}
            
        except Exception as error:
            self.error(f"第二阶段合并失败: {error}")
            return {"characters": [], "terms": []}

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

        sorted_sources = sorted(raw_grouped_inputs.keys(), key=lambda s: (-len(s), s))
        grouped_inputs, source_aliases, consumed_sources = {}, {}, set()

        for source in sorted_sources:
            if source in consumed_sources: continue
            merged_group = {"source": source, "merged_sources": [source], "candidates": list(raw_grouped_inputs[source].get("candidates", []))}
            grouped_inputs[source] = merged_group
            source_aliases[source] = source
            consumed_sources.add(source)

            for other_source in sorted_sources:
                if other_source in consumed_sources or other_source == source: continue
                if other_source in source:  # 短 source 挂靠
                    merged_group["merged_sources"].append(other_source)
                    merged_group["candidates"].extend(raw_grouped_inputs[other_source].get("candidates", []))
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
        system_prompt = (
            "你是一个本地化术语库规范化专家。你将收到一组经初步提取的“候选词组（Group）”。\n"
            "有时候相同的词汇会被误判为不同的类型（如既被识别为角色，又被识别为术语）。\n"
            "你的唯一任务是：综合判定每个 Group，裁决它最终属于“角色(characters)”还是“术语(terms)”，并提炼出一个最准确的结果。\n"
            "【严格执行以下规则】\n"
            "1. 唯一归属：同一个词不能既是角色又是术语，必须二选一。\n"
            "2. 主键保留：输出的 `source` 必须严格使用传入的 `主source`，绝不能随意篡改。\n"
            "3. 丢弃无价值词汇：如果某个 Group 里的词汇看起来是普通词语（如“今天”、“然后”），请直接忽略，不要输出它。\n"
            "4. 信息整合：如果推荐译名或备注有多个参考，请合并为你认为最合理的版本。\n"
            "【输出格式】\n"
            "必须输出合法的 JSON 代码块，严格遵守以下结构：\n"
            "```json\n"
            "{\n"
            "  \"characters\": [{\"source\": \"主source\", \"recommended_translation\": \"推荐译名\", \"gender\": \"分类属性\", \"note\": \"整合后的备注\"}],\n"
            "  \"terms\": [{\"source\": \"主source\", \"recommended_translation\": \"推荐译名\", \"category_path\": \"分类属性\", \"note\": \"整合后的备注\"}]\n"
            "}\n"
            "```"
        )
        
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
                }
                assigned_sources.add(source)

            for row in result.get("terms", []):
                source = str(row.get("source", "")).strip()
                source = self.grouped_stage_two_source_aliases.get(source, source)
                if not source or source in assigned_sources: continue
                merged_terms[source] = {
                    "source": source, "recommended_translation": str(row.get("recommended_translation", "")).strip(),
                    "category_path": str(row.get("category_path", "")).strip() or "其他", "note": str(row.get("note", "")).strip(),
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
                merged_terms[source] = {"source": source, "recommended_translation": trans, "category_path": cat, "note": " | ".join(notes)}
            else:
                gen = next((str(c.get("gender", "")).strip() for c in all_cands if str(c.get("gender", "")).strip() not in ["", "其他"]), "其他")
                merged_characters[source] = {"source": source, "recommended_translation": trans, "gender": gen, "note": " | ".join(notes)}

        # 3. 第一阶段禁翻项的清洗合并 (不走第二阶段 AI)
        merged_non_translate = {}
        for result in first_stage_results:
            for row in result.get("non_translate", []):
                marker = str(row.get("marker", "")).strip()
                if not marker or all(char.isspace() or char in self.COMMON_PUNCTUATION_CHARS for char in marker):
                    continue

                cat, note = str(row.get("category", "")).strip(), str(row.get("note", "")).strip()
                existing = merged_non_translate.setdefault(marker, {"marker": marker, "category": cat, "note": note})
                
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

    def _emit_progress_update(self, phase: str, phase_label: str, current: int, total: int, message: str, detail: str) -> None:
        """统一的进度更新接口"""
        self.emit(
            Base.EVENT.ANALYSIS_TASK_UPDATE,
            {
                "status": "running", "phase": phase, "phase_label": phase_label,
                "current": max(0, int(current or 0)), "total": max(0, int(total or 0)),
                "percent": self._calculate_progress_percent(phase, current, total),
                "message": message, "detail": detail,
            },
        )

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
            if Base.work_status == Base.STATUS.STOPING:
                return None

            try:
                # 1. 发送请求
                requester = LLMRequester()
                skip, _, response_content, _, _ = requester.sent_request(
                    [dict(msg) for msg in messages],
                    system_prompt,
                    self.config.get_active_platform_configuration(),
                )

                if skip:
                    if Base.work_status == Base.STATUS.STOPING: return None
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
                if Base.work_status == Base.STATUS.STOPING: return None
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
