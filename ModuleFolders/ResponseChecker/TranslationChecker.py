import time
from collections import defaultdict
from typing import List, Dict, Any, Tuple

from Base.Base import Base
from ModuleFolders.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Cache.CacheManager import CacheManager
from ModuleFolders.FileReader import ReaderUtil
from ModuleFolders.TaskExecutor import TranslatorUtil

# 定义结果码，便于UI判断
class CheckResult:
    SUCCESS_REPORT = "SUCCESS_REPORT"
    SUCCESS_JUDGE_PASS = "SUCCESS_JUDGE_PASS"
    SUCCESS_JUDGE_FAIL = "SUCCESS_JUDGE_FAIL"
    ERROR_CACHE = "ERROR_CACHE"
    ERROR_NO_TRANSLATION = "ERROR_NO_TRANSLATION"
    ERROR_NO_POLISH = "ERROR_NO_POLISH"
    ERROR_INVALID_LANG = "ERROR_INVALID_LANG"

class TranslationChecker(Base):
    """
    双模式语言检查。
    - 精准判断 (judge): 按块分析，精确定位语言比例异常的行
    - 宏观统计 (report): 对整个项目的文件进行语言统计，并报告
    """
    TARGET_LANGUAGE_RATIO_THRESHOLD = 0.75  # [判断模式] 目标语言在块中的占比阈值
    CHUNK_SIZE = 20                        # [判断模式] 每个检测块包含的行数

    def __init__(self, cache_manager: CacheManager):
        super().__init__()
        self.cache_manager = cache_manager
        self.config = self.load_config()

    def check_language(self, mode: str) -> Tuple[str, Dict]:
        """
        根据指定模式执行语言检查。
        - polish_judge:   [精准判断] 检测并判断润色文本。
        - polish:         [宏观统计] 报告润色文本的语言组成。
        - judge:          [精准判断] 检测并判断翻译文本。
        - (默认/其他):     [宏观统计] 报告翻译文本的语言组成。
        """
        start_time = time.time()

        pre_check_result, pre_check_data = self._perform_pre_checks(mode)
        if pre_check_result is not None:
            return pre_check_result, pre_check_data

        # 初始化检查参数
        is_judging = "judge" in mode
        check_target = "polished_text" if "polish" in mode else "translated_text"
        target_language_name = self.config.get("target_language", "english")
        target_language_code = TranslatorUtil.map_language_name_to_code(target_language_name)
        mode_text = self.tra("润色后文本") if "polish" in mode else self.tra("翻译后文本")

        if not target_language_code:
            self.error(self.tra("检查失败：无法将目标语言名称 '{}' 转换为有效的语言代码。请检查您的配置。").format(target_language_name))
            return CheckResult.ERROR_INVALID_LANG, {"lang_name": target_language_name}
        
        # 兼容繁中检测
        if target_language_code == 'zh-Hant':
            target_language_code = 'zh'

        self.info(self.tra("开始检查项目的{}...").format(mode_text))
        if is_judging:
            self.info(self.tra("模式: 精准判断，目标语言: {} ({})").format(target_language_name, target_language_code))
            self.info(self.tra("检测块大小: {}行, 块语言比例阈值: {:.0%}").format(self.CHUNK_SIZE, self.TARGET_LANGUAGE_RATIO_THRESHOLD))
        else:
            self.info(self.tra("模式: 宏观统计【将报告每个文件的整体语言组成】"))
        self.print("-" * 20)

        # 执行分析
        all_results = []
        try:
            for cache_file in self.cache_manager.project.files.values():
                if is_judging:
                    # [精准判断模式] 使用分块分析
                    file_analysis_result = self._analyze_file_in_chunks(cache_file, check_target, target_language_code)
                    if file_analysis_result and file_analysis_result["problematic_chunks"]:
                        all_results.append(file_analysis_result)
                else:
                    # [宏观统计模式] 使用整体文件分析
                    analysis_result = self._analyze_file_for_report(cache_file, check_target)
                    if analysis_result:
                        all_results.append(analysis_result)
        finally:
            ReaderUtil.close_lang_detector()
        self.info(self.tra("语言检查完成，耗时 {:.2f} 秒").format(time.time() - start_time))         

        # 生成报告
        self._print_report(all_results, is_judging, target_language_code, mode_text)
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

    def _perform_pre_checks(self, mode: str) -> Tuple[str | None, Dict]:
        """执行预检查，确保项目和缓存数据有效"""
        if not self.cache_manager.project or not self.cache_manager.project.files:
            self.error(self.tra("检查失败，请检查项目文件夹缓存是否正常"))
            return CheckResult.ERROR_CACHE, {}

        has_content = False
        check_target_attr = "polished_text" if "polish" in mode else "translated_text"
        status_to_check = TranslationStatus.POLISHED if "polish" in mode else TranslationStatus.TRANSLATED

        # 检查是否存在至少一个需要被检查的有效文本项
        for item in self.cache_manager.project.items_iter():
            if item.translation_status >= status_to_check and getattr(item, check_target_attr, "").strip():
                has_content = True
                break

        if not has_content:
            if "polish" in mode:
                self.error(self.tra("检查失败，请先执行润色流程"))
                return CheckResult.ERROR_NO_POLISH, {}
            else:
                self.error(self.tra("检查失败，请先执行翻译流程"))
                return CheckResult.ERROR_NO_TRANSLATION, {}
            
        return None, {}

    def _run_detection(self, items_to_check: List[CacheItem], check_target: str) -> list:
        """辅助函数，对给定的 CacheItem 列表运行语言检测。"""
        texts = [getattr(item, check_target, "") for item in items_to_check]
        # 使用一个临时的、不包含任何复杂数据的 CacheItem 列表进行检测
        dummy_items = [CacheItem(source_text=t) for t in texts]
        return ReaderUtil.detect_language_with_mediapipe(dummy_items, 0, None)


    def _analyze_file_in_chunks(self, cache_file, check_target: str, target_language_code: str) -> Dict[str, Any] | None:
        """
        [精准判断模式] 按块分析文件。如果块不符合要求，则进行行级分析。
        """
        items_with_text_and_indices = [
            (idx, item) for idx, item in enumerate(cache_file.items)
            if getattr(item, check_target, "").strip()
        ]
        if not items_with_text_and_indices:
            return None

        problematic_chunks = []
        for i in range(0, len(items_with_text_and_indices), self.CHUNK_SIZE):
            chunk_with_indices = items_with_text_and_indices[i : i + self.CHUNK_SIZE]
            chunk_items = [item for idx, item in chunk_with_indices] # 提取 item 用于检测

            # 一次性获取当前块所有行的检测结果
            detection_results = self._run_detection(chunk_items, check_target)

            # 一次循环处理，同时收集块统计和行级信息
            lang_counts = defaultdict(int)
            line_by_line_details = []
            for (original_idx, item), res in zip(chunk_with_indices, detection_results):
                # 使用安全的方式处理可能不完整的返回数据
                detected_lang = "N/A"
                confidence = 0.0
                text_content = getattr(item, check_target, "")

                # 检查返回结果是否有效且不是特殊标记
                if res and res[0] and res[0][0] not in ['no_text', 'symbols_only', 'un']:
                    result_tuple = res[0]
                    
                    # 安全地获取语言代码
                    detected_lang = result_tuple[0]
                    
                    # 安全获取置信度
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

            # 计算块的比例
            target_lang_count = lang_counts.get(target_language_code, 0)
            ratio = target_lang_count / total_valid_lines

            # 如果比例低于阈值，使用已收集的行级信息生成报告
            if ratio < self.TARGET_LANGUAGE_RATIO_THRESHOLD:
                mismatched_lines = [
                    detail for detail in line_by_line_details 
                    if detail["detected_lang"] != target_language_code
                ]
                
                if mismatched_lines:
                    first_item_line_num = chunk_with_indices[0][0] + 1
                    last_item_line_num = chunk_with_indices[-1][0] + 1
                    problematic_chunks.append({
                        "chunk_range": self.tra("行 {}-{}").format(first_item_line_num, last_item_line_num),
                        "ratio": ratio,
                        "mismatched_lines": mismatched_lines
                    })
        
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

    def _print_report(self, results: List[Dict], is_judging: bool, target_language_code: str, mode_text: str):
        """根据模式打印不同风格的报告。"""
        if not results:
            if is_judging:
                self.info(self.tra("检查通过：项目的所有文件 {} 均符合预期.").format(mode_text))
            else:
                self.info(self.tra("未在项目的 {} 中找到可供分析的文本内容.").format(mode_text))
            return

        # 根据模式选择报告格式
        if is_judging:
            # [精准判断模式] 的详细报告
            self.warning(self.tra("检测到 {} 个文件的 {} 中存在语言比例异常的文本块.").format(len(results), mode_text))
            self.warning(self.tra("目标语言 '{}' 占比低于 {:.0%} 的块将被列出.").format(target_language_code, self.TARGET_LANGUAGE_RATIO_THRESHOLD))
            self.print("")

            for res in results:
                cache_file = res["file_info"]
                self.info(self.tra("▼ 文件: {} (类型: {}, 编码: {})").format(cache_file.storage_path, cache_file.file_project_type, cache_file.encoding))
                
                for chunk in res["problematic_chunks"]:
                    self.warning(
                        self.tra("  └─ 问题区块: {} (目标语言占比: {:.2%})").format(chunk['chunk_range'], chunk['ratio'])
                    )
                    for line_info in chunk['mismatched_lines']:
                        text_preview = line_info['text'].strip().replace('\n', ' ')[:50]
                        self.error(
                            self.tra("    ├─ 行 {}: 检测为 [{}] (置信度: {:.2f}) -> \"{}...\"").format(
                                line_info['original_line_num'], 
                                line_info['detected_lang'], 
                                line_info['confidence'], 
                                text_preview
                            )
                        )
                self.print("") 
        else:
            # [宏观统计模式] 的概览报告
            self.info(self.tra("以下是各文件的 {} 语言组成统计报告:").format(mode_text))
            self.print("-" * 20)
            for res in results:
                self._print_report_mode_info(res["file_info"], res["stats_display"])
                self.print("") # 在文件报告之间添加空行

    def _print_report_mode_info(self, cache_file, stats_display):
        """[宏观统计模式] 打印单个文件的统计信息。"""
        formatted_stats = [(lang, f"{conf:.2%}") for lang, conf in stats_display]

        self.info(self.tra("文件: {}").format(cache_file.storage_path))
        self.info(self.tra("  ├─ 类型: {}").format(cache_file.file_project_type))
        self.info(self.tra("  ├─ 编码: {}").format(cache_file.encoding))
        self.info(self.tra("  └─ 语言统计: {}").format(formatted_stats))