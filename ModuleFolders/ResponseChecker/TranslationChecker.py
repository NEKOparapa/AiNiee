import time
from collections import defaultdict
from typing import List, Dict, Any

from Base.Base import Base
from ModuleFolders.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Cache.CacheManager import CacheManager
from ModuleFolders.FileReader import ReaderUtil
from ModuleFolders.TaskExecutor import TranslatorUtil

class TranslationChecker(Base):
    """
    双模式语言检查。
    - 精准判断 (judge): 按块分析，精确定位语言比例异常的行
    - 宏观统计 (report): 对整个项目的文件进行语言统计，并报告
    """
    TARGET_LANGUAGE_RATIO_THRESHOLD = 0.6  # [判断模式] 目标语言在块中的占比阈值
    CHUNK_SIZE = 20                        # [判断模式] 每个检测块包含的行数

    def __init__(self, cache_manager: CacheManager):
        super().__init__()
        self.cache_manager = cache_manager
        self.config = self.load_config()

    def check_language(self, mode: str):
        """
        根据指定模式执行语言检查。
        - polish_judge:   [精准判断] 检测并判断润色文本。
        - polish:         [宏观统计] 报告润色文本的语言组成。
        - judge:          [精准判断] 检测并判断翻译文本。
        - (默认/其他):     [宏观统计] 报告翻译文本的语言组成。
        """
        start_time = time.time()

        if not self._perform_pre_checks(mode):
            return

        # 初始化检查参数
        is_judging = "judge" in mode
        check_target = "polished_text" if "polish" in mode else "translated_text"
        target_language_name = self.config.get("target_language", "english")
        target_language_code = TranslatorUtil.map_language_name_to_code(target_language_name)
        mode_text = "润色后文本" if "polish" in mode else "翻译后文本"

        if not target_language_code:
            self.error(f"检查失败：无法将目标语言名称 '{target_language_name}' 转换为有效的语言代码。请检查您的配置。")
            return
        
        # 兼容繁中检测
        if target_language_code == 'zh-Hant':
            target_language_code = 'zh'

        # 打印检查头部信息
        self.info(f"开始检查项目的 {mode_text}...")
        if is_judging:
            self.info(f"模式: 精准判断。目标语言: {target_language_name} ({target_language_code})")
            self.info(f"检测块大小: {self.CHUNK_SIZE}行, 块语言比例阈值: {self.TARGET_LANGUAGE_RATIO_THRESHOLD:.0%}")
        else:
            self.info(f"模式: 宏观统计。将报告每个文件的整体语言组成。")
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

        # 生成报告
        self._print_report(all_results, is_judging, target_language_code, mode_text)
        self.info(f"语言检查完成，耗时 {(time.time() - start_time):.2f} 秒")

    def _perform_pre_checks(self, mode: str) -> bool:
        """执行预检查，确保项目和缓存数据有效。"""
        if not self.cache_manager.project or not self.cache_manager.project.files:
            self.error("检查失败，请检查项目文件夹缓存是否正常")
            return False

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
                self.error("检查失败，请先执行润色流程")
            else:
                self.error("检查失败，请先执行翻译流程")
            return False
            
        return True

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
        items_with_text = [
            item for item in cache_file.items 
            if getattr(item, check_target, "").strip()
        ]
        if not items_with_text:
            return None

        problematic_chunks = []
        for i in range(0, len(items_with_text), self.CHUNK_SIZE):
            chunk_items = items_with_text[i : i + self.CHUNK_SIZE]
            detection_results = self._run_detection(chunk_items, check_target)

            # 统计块内语言分布
            lang_counts = defaultdict(int)
            for res in detection_results:
                if res[0] and res[0][0] not in ['no_text', 'symbols_only', 'un']:
                    lang_counts[res[0][0]] += 1
            
            total_valid_lines = sum(lang_counts.values())
            if total_valid_lines == 0:
                continue

            # 计算目标语言比例
            target_lang_count = lang_counts.get(target_language_code, 0)
            ratio = target_lang_count / total_valid_lines

            # 如果块的比例低于阈值，则逐行分析并记录问题行
            if ratio < self.TARGET_LANGUAGE_RATIO_THRESHOLD:
                mismatched_lines = []
                for item, res in zip(chunk_items, detection_results):
                    detected_lang, confidence = "N/A", 0.0
                    if res[0] and res[0][0] not in ['no_text', 'symbols_only', 'un']:
                        detected_lang, confidence = res[0]

                    if detected_lang != target_language_code:
                        mismatched_lines.append({
                            "item": item,
                            "detected_lang": detected_lang,
                            "confidence": confidence,
                            "text": getattr(item, check_target)
                        })
                
                if mismatched_lines:
                    first_item_index = chunk_items[0].text_index
                    last_item_index = chunk_items[-1].text_index
                    problematic_chunks.append({
                        "chunk_range": f"行 {first_item_index}-{last_item_index}",
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
                self.info(f"检查通过：项目的所有文件 {mode_text} 均符合预期。")
            else:
                self.info(f"未在项目的 {mode_text} 中找到可供分析的文本内容。")
            return

        # 根据模式选择报告格式
        if is_judging:
            # [精准判断模式] 的详细报告
            self.warning(f"检测到 {len(results)} 个文件的 {mode_text} 中存在语言比例异常的文本块。")
            self.warning(f"目标语言 '{target_language_code}' 占比低于 {self.TARGET_LANGUAGE_RATIO_THRESHOLD:.0%} 的块将被列出。")
            self.print("")

            for res in results:
                cache_file = res["file_info"]
                self.info(f"▼ 文件: {cache_file.storage_path} (类型: {cache_file.file_project_type}, 编码: {cache_file.encoding})")
                
                for chunk in res["problematic_chunks"]:
                    self.warning(
                        f"  └─ 问题区块: {chunk['chunk_range']} (目标语言占比: {chunk['ratio']:.2%})"
                    )
                    for line_info in chunk['mismatched_lines']:
                        text_preview = line_info['text'].strip().replace('\n', ' ')[:50]
                        self.error(
                            f"    ├─ 行 {line_info['item'].text_index}: "
                            f"检测为 [{line_info['detected_lang']}] (置信度: {line_info['confidence']:.2f}) "
                            f"-> \"{text_preview}...\""
                        )
                self.print("") 
        else:
            # [宏观统计模式] 的概览报告
            self.info(f"以下是各文件的 {mode_text} 语言组成统计报告:")
            self.print("-" * 20)
            for res in results:
                self._print_report_mode_info(res["file_info"], res["stats_display"])
                self.print("") # 在文件报告之间添加空行

    def _print_report_mode_info(self, cache_file, stats_display):
        """[宏观统计模式] 打印单个文件的统计信息。"""
        formatted_stats = [(lang, f"{conf:.2%}") for lang, conf in stats_display]

        self.info(f"文件: {cache_file.storage_path}")
        self.info(f"  ├─ 类型: {cache_file.file_project_type}")
        self.info(f"  ├─ 编码: {cache_file.encoding}")
        self.info(f"  └─ 语言统计: {formatted_stats}")