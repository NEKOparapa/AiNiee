import os
import time
from collections import defaultdict
from typing import List, Dict, Any, Tuple

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Domain.FileReader import ReaderUtil
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.TaskExecutor import TranslatorUtil
from ModuleFolders.Service.TranslationChecker.CheckResult import CheckResult


class LanguageChecker(ConfigMixin, LogMixin, Base):
    """
    双模式语言检查。
    """

    def __init__(self, cache_manager: CacheManager):
        super().__init__()
        self.cache_manager = cache_manager
        self.config = self.load_config()
        self._last_results = []
        self._last_target_language_name = self.config.get("target_language", "english")
        self._last_target_language_code = TranslatorUtil.map_language_name_to_code(self._last_target_language_name) or self._last_target_language_name

    def _build_error_type(self, detected_lang: str | None, target_lang: str | None = None) -> str:
        detected_lang = detected_lang or "unknown"
        target_lang = target_lang or self._last_target_language_code or self._last_target_language_name or "unknown"
        return "语言不匹配(检测: {}, 目标: {})".format(detected_lang, target_lang)

    def run_check(self, params: dict) -> Tuple[str, Any]:
        """
        语言检查入口，返回新的结果结构给UI使用
        """
        mode = params.get("mode", "report")

        #  获取并校验动态参数
        chunk_size = params.get("chunk_size", 20)
        try:
            chunk_size = int(chunk_size)
            if chunk_size <= 0: chunk_size = 20
        except: chunk_size = 20

        threshold = params.get("threshold", 0.75)
        try:
            threshold = float(threshold)
            if threshold > 1.0:
                threshold = threshold / 100.0
            if not (0.0 < threshold <= 1.0):
                threshold = 0.75
        except:
            threshold = 0.75

        lang_result_code, lang_data = self.check_language(mode, chunk_size, threshold)

        if lang_result_code.startswith("ERROR"):
            return lang_result_code, lang_data

        issue_rows = []
        report_rows = []

        if "judge" in mode:
            issue_rows = self._collect_lang_errors_from_cache()
            if not issue_rows and self._last_results:
                issue_rows = self._build_language_issue_rows_from_results(self._last_results)
        else:
            report_rows = self._build_language_report_rows(self._last_results)

        return CheckResult.SUCCESS_LANGUAGE_RESULT, {
            "mode": mode,
            "target_language": self._last_target_language_name,
            "report_rows": report_rows,
            "issue_rows": issue_rows,
            "passed": not issue_rows if "judge" in mode else True,
        }

    def _collect_lang_errors_from_cache(self) -> List[Dict]:
        """
        辅助函数：遍历缓存，查找被 check_language 打上标记的项
        """
        errors = []
        flag_key = "language_mismatch_translation"
        detected_lang_key = f"{flag_key}_detected_lang"
        target_lang_key = f"{flag_key}_target_lang"
        check_attr = "translated_text"

        for file_path, file_obj in self.cache_manager.project.files.items():
            file_name = os.path.basename(file_path)
            for item in file_obj.items:
                # 检查 extra 字典是否存在且标记为 True
                if item.extra and item.extra.get(flag_key) is True:
                    text_content = getattr(item, check_attr, "")
                    detected_lang = item.extra.get(detected_lang_key)
                    target_lang = item.extra.get(target_lang_key)
                    errors.append({
                        "row_id": f"{file_name} : {item.text_index + 1}",
                        "error_type": self._build_error_type(detected_lang, target_lang),
                        "source": item.source_text,
                        "check_text": text_content,
                        "file_path": file_path,
                        "text_index": item.text_index,
                        "target_field": check_attr
                    })
        return errors

    def _build_language_issue_rows_from_results(self, results: List[Dict]) -> List[Dict]:
        """
        辅助函数：从本次检查结果中构建问题列表
        """
        errors = []
        seen = set()
        check_attr = "translated_text"

        for result in results:
            cache_file = result.get("file_info")
            if cache_file is None:
                continue

            file_path = getattr(cache_file, "storage_path", "")
            file_name = os.path.basename(file_path)

            for chunk in result.get("problematic_chunks", []):
                for line_info in chunk.get("mismatched_lines", []):
                    item_index = line_info.get("original_line_num", 0) - 1
                    if item_index < 0 or item_index >= len(cache_file.items):
                        continue

                    dedupe_key = (file_path, item_index)
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)

                    item = cache_file.items[item_index]
                    text_content = getattr(item, check_attr, "")
                    detected_lang = line_info.get("detected_lang")
                    errors.append({
                        "row_id": f"{file_name} : {item.text_index + 1}",
                        "error_type": self._build_error_type(detected_lang),
                        "source": item.source_text,
                        "check_text": text_content,
                        "file_path": file_path,
                        "text_index": item.text_index,
                        "target_field": check_attr
                    })

        return errors

    def _build_language_report_rows(self, results: List[Dict]) -> List[Dict]:
        """
        辅助函数：从宏观统计结果中构建只读报告列表
        """
        report_rows = []

        for result in results:
            cache_file = result.get("file_info")
            if cache_file is None:
                continue

            stats_display = result.get("stats_display", [])
            formatted_stats = [f"{lang}: {confidence:.2%}" for lang, confidence in stats_display]
            report_rows.append({
                "file_path": getattr(cache_file, "storage_path", ""),
                "file_type": getattr(cache_file, "file_project_type", ""),
                "encoding": getattr(cache_file, "encoding", ""),
                "stats_text": " / ".join(formatted_stats)
            })

        return report_rows

    # --- 语言检查主流程 ---
    def check_language(self, mode: str, chunk_size: int = 20, threshold: float = 0.75) -> Tuple[str, Dict]:
        start_time = time.time()
        self._last_results = []

        pre_check_result, pre_check_data = self._perform_pre_checks(mode)
        if pre_check_result is not None:
            return pre_check_result, pre_check_data

        # 初始化检查参数
        is_judging = "judge" in mode
        check_target = "translated_text"
        flag_key = "language_mismatch_translation"
        target_language_name = self.config.get("target_language", "english")
        target_language_code = TranslatorUtil.map_language_name_to_code(target_language_name)
        mode_text = "翻译后文本"
        self._last_target_language_name = target_language_name

        if not target_language_code:
            self.error("检查失败：无法将目标语言名称 '{}' 转换为有效的语言代码。请检查您的配置。".format(target_language_name))
            return CheckResult.ERROR_INVALID_LANG, {"lang_name": target_language_name}

        # 兼容繁中检测
        if target_language_code == 'zh-Hant':
            target_language_code = 'zh'
        self._last_target_language_code = target_language_code

        self.info("开始检查项目的{}...".format(mode_text))
        if is_judging:
            self.info("模式: 精准判断，目标语言: {} ({})".format(target_language_name, target_language_code))
            #  使用传入的参数打印日志
            self.info("检测块大小: {}行, 块语言比例阈值: {:.0%}".format(chunk_size, threshold))
        else:
            self.info("模式: 宏观统计【将报告每个文件的整体语言组成】")
        self.print("-" * 20)

        #检查前查看是否有标记
        self.info("正在清除旧的语言检查标记...")
        #遍历所有 item
        for item in self.cache_manager.project.items_iter():
            if item.extra:
                item.extra.pop("language_mismatch_translation", None)
                item.extra.pop("language_mismatch_polish", None)
                item.extra.pop("language_mismatch_translation_detected_lang", None)
                item.extra.pop("language_mismatch_translation_target_lang", None)

                # 如果 extra 字典在移除标记后变为空，将其设为 None 以保持缓存干净
                if not item.extra:
                    item.extra = None
        self.info("旧标记已清除。现在开始新的检查...")
        self.print("-" * 20)


        # 执行分析
        all_results = []
        try:
            for cache_file in self.cache_manager.project.files.values():
                if is_judging:
                    # [精准判断模式] 使用分块分析
                    file_analysis_result = self._analyze_file_in_chunks(cache_file, check_target, target_language_code, flag_key, chunk_size, threshold)
                    if file_analysis_result and file_analysis_result["problematic_chunks"]:
                        all_results.append(file_analysis_result)
                else:
                    # [宏观统计模式] 使用整体文件分析
                    analysis_result = self._analyze_file_for_report(cache_file, check_target)
                    if analysis_result:
                        all_results.append(analysis_result)
        finally:
            ReaderUtil.close_lang_detector()
        self.info("语言检查完成，耗时 {:.2f} 秒".format(time.time() - start_time))

        # 如果在精准判断模式下发现了问题，则保存带有标记的缓存
        if is_judging and all_results:
            self.info("检测到语言不匹配项，正在将标记保存到磁盘...")
            try:
                # 从配置中获取正确的输出路径。
                config = self.load_config()
                output_path = config.get("label_output_path")

                if True:
                    #为 CacheManager 设置必要的保存路径

                    # 立即执行保存操作
                    self.cache_manager.save_to_file()

                    self.info("标记已成功保存到缓存文件。")
                else:
                    self.warning("无法保存标记：输出路径 '{}' 未配置或无效".format(output_path))
            except Exception as e:
                self.error("保存标记到缓存时发生错误: {}".format(e))

        self._last_results = all_results

        # 生成报告
        self._print_report(all_results, is_judging, target_language_code, mode_text, threshold)
        if all_results:
            self.print("\n")


        # 返回结果码
        if is_judging:
            if not all_results:
                return CheckResult.SUCCESS_JUDGE_PASS, {"target_language": target_language_name}
            else:
                return CheckResult.SUCCESS_JUDGE_FAIL, {"target_language": target_language_name}
        else:
            return CheckResult.SUCCESS_REPORT, {}

    # 辅助方法
    def _perform_pre_checks(self, mode: str) -> Tuple[str | None, Dict]:
        """Run lightweight pre-checks before language detection."""
        if not self.cache_manager.project or not self.cache_manager.project.files:
            self.error("Language check pre-check failed: cache data is unavailable.")
            return CheckResult.ERROR_CACHE, {}

        project_id = getattr(self.cache_manager.project, "project_id", "")
        stats_payload = self.cache_manager.read_project_statistics(project_id)
        if not isinstance(stats_payload, dict):
            self.error("Language check pre-check failed: ProjectStatistics.json is missing or invalid.")
            return CheckResult.ERROR_CACHE, {}

        translated_line = CacheManager._parse_int(stats_payload.get("line", 0))
        if translated_line <= 1:
            self.error("Language check pre-check failed: translated line count is not greater than 1.")
            return CheckResult.ERROR_NO_TRANSLATION, {}

        return None, {}

    def _run_detection(self, items_to_check: List[CacheItem], check_target: str) -> list:
        """辅助函数，对给定的 CacheItem 列表运行语言检测。"""
        texts = [getattr(item, check_target, "") for item in items_to_check]
        # 使用一个临时的、不包含任何复杂数据的 CacheItem 列表进行检测
        dummy_items = [CacheItem(source_text=t) for t in texts]
        return ReaderUtil.detect_language_with_mediapipe(dummy_items, 0, None)


    def _analyze_file_in_chunks(self, cache_file, check_target: str, target_language_code: str, flag_key: str, chunk_size: int, threshold: float) -> Dict[str, Any] | None:
        """
        [精准判断模式] 按块分析文件。
        修改优化：使用硬编码的 BATCH_SIZE 进行快速检测，使用 chunk_size (UI参数) 进行逻辑窗口评估。
        """
        # 1. 筛选出有效文本行 (保留原始索引)
        items_with_text_and_indices = [
            (idx, item) for idx, item in enumerate(cache_file.items)
            if getattr(item, check_target, "").strip()
        ]
        if not items_with_text_and_indices:
            return None

        # 2. 批量检测
        # 硬编码较大的 Batch Size 确保检测速度
        DETECTION_BATCH_SIZE = 128
        all_detection_results = []

        # 提取纯 Item 列表用于检测
        all_items_to_detect = [item for _, item in items_with_text_and_indices]

        for i in range(0, len(all_items_to_detect), DETECTION_BATCH_SIZE):
            batch_items = all_items_to_detect[i : i + DETECTION_BATCH_SIZE]
            batch_results = self._run_detection(batch_items, check_target)
            all_detection_results.extend(batch_results)

        #返回行数检查
        if len(all_detection_results) != len(items_with_text_and_indices):
            self.error("检测结果数量({})与文本行数({})不一致！".format(len(all_detection_results), len(items_with_text_and_indices)))
            return None

# 3. 评估
        problematic_chunks = []
        total_items = len(items_with_text_and_indices)

        for i in range(0, total_items, chunk_size):
            # 如果剩余未处理的行数不足一个块(且不是第一块)则跳过
            if i > 0 and (total_items - i) < chunk_size:
                continue

            # 计算结束索引：剩余不足的块，将合并到当前块处理
            current_end = i + chunk_size
            if current_end < total_items and (total_items - current_end) < chunk_size:
                current_end = total_items

            # 获取当前窗口的切片 (Item信息 和 预先计算好的检测结果)
            chunk_with_indices = items_with_text_and_indices[i : current_end]
            chunk_detection_results = all_detection_results[i : current_end]

            # 统计当前窗口
            lang_counts = defaultdict(int)
            line_by_line_details = []

            for (original_idx, item), res in zip(chunk_with_indices, chunk_detection_results):
                detected_lang = "N/A"
                confidence = 0.0
                text_content = getattr(item, check_target, "")

                if res and res[0] and res[0][0] not in ['no_text', 'symbols_only', 'un']:
                    result_tuple = res[0]
                    detected_lang = result_tuple[0]
                    if len(result_tuple) > 1:
                        raw_confidence = result_tuple[1]
                        if isinstance(raw_confidence, (tuple, list)) and raw_confidence:
                           confidence = raw_confidence[0]
                        elif isinstance(raw_confidence, (int, float)):
                           confidence = raw_confidence

                    lang_counts[detected_lang] += 1

                line_by_line_details.append({
                    "original_line_num": original_idx + 1,
                    "detected_lang": detected_lang,
                    "confidence": confidence,
                    "text": text_content
                })

            total_valid_lines = sum(lang_counts.values())
            if total_valid_lines == 0:
                continue

            # 计算窗口的比例
            target_lang_count = lang_counts.get(target_language_code, 0)
            ratio = target_lang_count / total_valid_lines

            # 判定逻辑
            if ratio < threshold:
                mismatched_lines = [
                    detail for detail in line_by_line_details
                    if detail["detected_lang"] != target_language_code
                ]

                if mismatched_lines:
                    first_item_line_num = chunk_with_indices[0][0] + 1
                    last_item_line_num = chunk_with_indices[-1][0] + 1
                    problematic_chunks.append({
                        "chunk_range": "行 {}-{}".format(first_item_line_num, last_item_line_num),
                        "ratio": ratio,
                        "mismatched_lines": mismatched_lines
                    })

                    # 打标记
                    for line_info in mismatched_lines:
                        item_index = line_info['original_line_num'] - 1
                        item_to_flag = cache_file.items[item_index]
                        if item_to_flag.extra is None:
                            item_to_flag.extra = {}
                        item_to_flag.extra[flag_key] = True
                        item_to_flag.extra[f"{flag_key}_detected_lang"] = line_info["detected_lang"]
                        item_to_flag.extra[f"{flag_key}_target_lang"] = target_language_code

        if not problematic_chunks:
            return None

        return {
            "file_info": cache_file,
            "problematic_chunks": problematic_chunks
        }

    def _analyze_file_for_report(self, cache_file, check_target: str) -> Dict[str, Any] | None:
        """[宏观统计模式] 对单个文件进行整体语言统计。"""
        items_with_text = [
            item for item in cache_file.items
            if getattr(item, check_target, "").strip()
        ]
        if not items_with_text:
            return None

        # 复用检测逻辑
        detection_results = self._run_detection(items_with_text, check_target)

        # 统计文件内所有语言的行数
        lang_counts = defaultdict(int)
        for res in detection_results:
            if res[0] and res[0][0] not in ['no_text', 'symbols_only', 'un']:
                lang_counts[res[0][0]] += 1

        total_valid_lines = sum(lang_counts.values())
        if total_valid_lines == 0:
            return None

        # 生成用于报告的语言统计信息
        sorted_langs = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)
        stats_display = [(lang, count / total_valid_lines) for lang, count in sorted_langs]

        return {
            "file_info": cache_file,
            "stats_display": stats_display
        }

    def _print_report(self, results: List[Dict], is_judging: bool, target_language_code: str, mode_text: str, threshold: float = 0.75):
        """根据模式打印不同风格的报告。"""
        if not results:
            if is_judging:
                self.info("检查通过：项目的所有文件 {} 均符合预期.".format(mode_text))
            else:
                self.info("未在项目的 {} 中找到可供分析的文本内容.".format(mode_text))
            return

        # 根据模式选择报告格式
        if is_judging:
            # [精准判断模式] 的详细报告
            self.warning("检测到 {} 个文件的 {} 中存在语言比例异常的文本块.".format(len(results), mode_text))
            self.warning("目标语言 '{}' 占比低于 {:.0%} 的块将被列出.".format(target_language_code, threshold))
            self.print("")

            for res in results:
                cache_file = res["file_info"]
                self.info("▼ 文件: {} (类型: {}, 编码: {})".format(cache_file.storage_path, cache_file.file_project_type, cache_file.encoding))

                for chunk in res["problematic_chunks"]:
                    self.warning(
                        "  └─ 问题区块: {} (目标语言占比: {:.2%})".format(chunk['chunk_range'], chunk['ratio'])
                    )
                    for line_info in chunk['mismatched_lines']:
                        text_preview = line_info['text'].strip().replace('\n', ' ')[:50]
                        self.error(
                            "    ├─ 行 {}: 检测为 [{}] (置信度: {:.2f}) -> \"{}...\"".format(
                                line_info['original_line_num'],
                                line_info['detected_lang'],
                                line_info['confidence'],
                                text_preview
                            )
                        )
                self.print("")
        else:
            # [宏观统计模式] 的概览报告
            self.info("以下是各文件的 {} 语言组成统计报告:".format(mode_text))
            self.print("-" * 20)
            for res in results:
                self._print_report_mode_info(res["file_info"], res["stats_display"])
                self.print("") # 在文件报告之间添加空行

    def _print_report_mode_info(self, cache_file, stats_display):
        """[宏观统计模式] 打印单个文件的统计信息。"""
        formatted_stats = [(lang, f"{conf:.2%}") for lang, conf in stats_display]

        self.info("文件: {}".format(cache_file.storage_path))
        self.info("  ├─ 类型: {}".format(cache_file.file_project_type))
        self.info("  ├─ 编码: {}".format(cache_file.encoding))
        self.info("  └─ 语言统计: {}".format(formatted_stats))
