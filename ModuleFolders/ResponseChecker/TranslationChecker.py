import os
import time
import re
import json
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
    HAS_RULE_ERRORS = "HAS_RULE_ERRORS"  # 存在需要列表展示的错误
    ERROR_CACHE = "ERROR_CACHE"
    ERROR_NO_TRANSLATION = "ERROR_NO_TRANSLATION"
    ERROR_NO_POLISH = "ERROR_NO_POLISH"
    ERROR_INVALID_LANG = "ERROR_INVALID_LANG"

class TranslationChecker(Base):
    """
    双模式语言检查。
    """
    TARGET_LANGUAGE_RATIO_THRESHOLD = 0.75  # [精准判断] 目标语言在块中的占比阈值
    CHUNK_SIZE = 20                         # [精准判断] 每个检测块包含的行数

    def __init__(self, cache_manager: CacheManager):
        super().__init__()
        self.cache_manager = cache_manager
        self.config = self.load_config()

    # --- 主检查流程 ---
    def check_process(self, params: dict) -> Tuple[str, Any]:
        """
        主检查流程
        """
        target = params.get("target", "translate")
        mode = params.get("mode", "report")
        rules = params.get("rules", {})

        # 1. 兼容逻辑
        legacy_mode_str = f"{target}_{mode}" if target == "polish" else mode
        if mode == "report" and target == "polish": legacy_mode_str = "polish"
        
        # 2. 执行原有的语言检测
        # 这个函数跑完后，有问题的 CacheItem 已经被打上了 extra 标记
        lang_result_code, lang_data = self.check_language(legacy_mode_str)

        # 如果基础检查失败（如无缓存），直接返回
        if lang_result_code.startswith("ERROR"):
            return lang_result_code, lang_data

        # 3. 执行规则检测
        all_errors = self._check_rules(target, rules)

        # 4. 从缓存中收集刚才被 check_language 标记的错误
        # 只有在"精准判断"模式下，且语言检测发现问题时才收集
        if "judge" in mode:
            lang_errors = self._collect_lang_errors_from_cache(target)
            if lang_errors:
                all_errors.extend(lang_errors)

        # 5. 如果收集到了任何错误（规则错误 或 语言标记错误），都强制返回 HAS_RULE_ERRORS
        if all_errors:
            return CheckResult.HAS_RULE_ERRORS, all_errors
        
        return lang_result_code, lang_data

    def _collect_lang_errors_from_cache(self, target_type: str) -> List[Dict]:
        """
        辅助函数：遍历缓存，查找被 check_language 打上标记的项
        """
        errors = []
        # 确定标记键和检查属性
        flag_key = "language_mismatch_polish" if target_type == "polish" else "language_mismatch_translation"
        check_attr = "polished_text" if target_type == "polish" else "translated_text"

        for file_path, file_obj in self.cache_manager.project.files.items():
            file_name = os.path.basename(file_path)
            for item in file_obj.items:
                # 检查 extra 字典是否存在且标记为 True
                if item.extra and item.extra.get(flag_key) is True:
                    text_content = getattr(item, check_attr, "")
                    errors.append({
                        "row_id": f"{file_name} : {item.text_index + 1}",
                        "error_type": self.tra("语言比例异常"), # 由于 check_language 没返回具体检测到的语言，只能显示通用错误
                        "source": item.source_text,
                        "check_text": text_content,
                        "file_path": file_path,
                        "text_index": item.text_index,
                        "target_field": check_attr
                    })
        return errors

    # --- 语言检查主流程 ---
    def check_language(self, mode: str) -> Tuple[str, Dict]:
        start_time = time.time()

        pre_check_result, pre_check_data = self._perform_pre_checks(mode)
        if pre_check_result is not None:
            return pre_check_result, pre_check_data

        # 初始化检查参数
        is_judging = "judge" in mode
        check_target = "polished_text" if "polish" in mode else "translated_text"
        flag_key = "language_mismatch_polish" if "polish" in mode else "language_mismatch_translation" #缓存标记
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

        #检查前查看是否有标记
        self.info(self.tra("正在清除旧的语言检查标记..."))
        ## 定义需要清除的标记键
        flag_key_translation = "language_mismatch_translation"
        flag_key_polish = "language_mismatch_polish"

        #遍历所有 item
        for item in self.cache_manager.project.items_iter():
            if item.extra:
                #安全的移除键
                item.extra.pop(flag_key_translation, None)
                item.extra.pop(flag_key_polish, None)

                # 如果 extra 字典在移除标记后变为空，将其设为 None 以保持缓存干净
                if not item.extra:
                    item.extra = None
        self.info(self.tra("旧标记已清除。现在开始新的检查..."))
        self.print("-" * 20)


        # 执行分析
        all_results = []
        try:
            for cache_file in self.cache_manager.project.files.values():
                if is_judging:
                    # [精准判断模式] 使用分块分析
                    file_analysis_result = self._analyze_file_in_chunks(cache_file, check_target, target_language_code, flag_key)
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

        # 如果在精准判断模式下发现了问题，则保存带有标记的缓存
        if is_judging and all_results:
            self.info(self.tra("检测到语言不匹配项，正在将标记保存到磁盘..."))
            try:
                # 从配置中获取正确的输出路径。
                config = self.load_config()
                output_path = config.get("label_output_path")

                if output_path and os.path.isdir(output_path):
                    #为 CacheManager 设置必要的保存路径
                    self.cache_manager.save_to_file_require_path = output_path

                    # 立即执行保存操作
                    self.cache_manager.save_to_file()

                    self.info(self.tra("标记已成功保存到缓存文件。"))
                else:
                    self.warning(self.tra("无法保存标记：输出路径 '{}' 未配置或无效").format(output_path))
            except Exception as e:
                self.error(self.tra("保存标记到缓存时发生错误: {}").format(e))

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

    # --- 规则检查主流程 ---
    def _check_rules(self, target_type: str, rules_config: dict) -> List[Dict]:
        if not any(rules_config.values()):
            return []

        self.info(self.tra("开始执行规则检查..."))
        errors_list = []

        # 准备正则表达式模式
        patterns = []
        if rules_config.get("auto_process"):
            patterns = self._prepare_regex_patterns(rules_config.get("exclusion", False))
        
        # 准备禁翻表数据
        exclusion_data = self.config.get("exclusion_list_data", []) if rules_config.get("exclusion") else []
        check_attr = "polished_text" if target_type == "polish" else "translated_text"
        
        # 准备术语表数据
        term_data = []
        if rules_config.get("terminology"):
            term_data = self.config.get("prompt_dictionary_data", [])

        for file_path, file_obj in self.cache_manager.project.files.items():
            file_name = os.path.basename(file_path)
            for item in file_obj.items:
                text_content = getattr(item, check_attr, "")
                # 跳过空文本或被排除的文本
                if not text_content or not item.source_text or item.translation_status == TranslationStatus.EXCLUDED:
                    continue
                
                current_errors = []

                # 1. 禁翻表
                if rules_config.get("exclusion") and exclusion_data:
                    current_errors.extend(self._rule_check_exclusion(item.source_text, text_content, exclusion_data))
                # 2. 术语表
                if rules_config.get("terminology") and term_data:
                    current_errors.extend(self._rule_check_terminology(item.source_text, text_content, term_data))
                # 3. 自动处理
                if rules_config.get("auto_process") and patterns:
                    current_errors.extend(self._rule_check_auto_process(item.source_text, text_content, patterns))
                # 4. 占位符
                if rules_config.get("placeholder"):
                    current_errors.extend(self._rule_check_placeholder(text_content))
                # 5. 数字序号
                if rules_config.get("number"):
                    current_errors.extend(self._rule_check_number(text_content))
                # 6. 示例复读
                if rules_config.get("example"):
                    current_errors.extend(self._rule_check_example(text_content))
                # 7. 换行符
                if rules_config.get("newline"):
                    current_errors.extend(self._rule_check_newline(item.source_text, text_content))

                # 收集结果
                for err in current_errors:
                    errors_list.append({
                        "row_id": f"{file_name} : {item.text_index + 1}",
                        "error_type": err,
                        "source": item.source_text,
                        "check_text": text_content,
                        "file_path": file_path,
                        "text_index": item.text_index,
                        "target_field": check_attr
                    })
        
        self.info(self.tra("规则检查完成，发现 {} 个问题。").format(len(errors_list)))
        return errors_list

    # --- 规则检查辅助方法 ---
    def _rule_check_terminology(self, src, dst, data):
        errs = []
        for term in data:
            if isinstance(term, dict):
                src_term = term.get("src")
                dst_term = term.get("dst")
                # 确保 src_term 和 dst_term 都存在且非空
                if src_term and dst_term:
                    # 简单的包含检查
                    if src_term in src:
                        if dst_term not in dst:
                            # 使用简短的错误描述以便在表格中显示
                            err_msg = self.tra("术语缺失: {}").format(dst_term)
                            if err_msg not in errs:
                                errs.append(err_msg)
        return errs
    
    def _prepare_regex_patterns(self, include_exclusion: bool):
        patterns = []
        regex_file = os.path.join(".", "Resource", "Regex", "check_regex.json")
        if os.path.exists(regex_file):
            try:
                with open(regex_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    patterns.extend([i["regex"] for i in data if "regex" in i])
            except: pass
        
        if include_exclusion:
            ex_data = self.config.get("exclusion_list_data", [])
            for item in ex_data:
                if item.get("regex"): patterns.append(item["regex"])
                elif item.get("markers"): patterns.append(re.escape(item["markers"]))
        return patterns

    def _rule_check_exclusion(self, src, dst, data):
        errs = []
        for item in data:
            regex = item.get("regex")
            markers = item.get("markers")
            pat = regex if regex else (re.escape(markers) if markers else None)
            if pat:
                try:
                    for match in re.finditer(pat, src):
                        if match.group(0) not in dst:
                            if self.tra("禁翻表错误") not in errs: errs.append(self.tra("禁翻表错误"))
                            break 
                except: continue
        return errs

    def _rule_check_auto_process(self, src, dst, patterns):
        errs = []
        _src = src.rstrip('\n')
        _dst = dst.rstrip('\n')
        for pat in patterns:
            try:
                for match in re.finditer(pat, _src):
                    if match.group(0) not in _dst:
                        if self.tra("自动处理错误") not in errs: errs.append(self.tra("自动处理错误"))
                        break
            except: continue
        return errs

    def _rule_check_placeholder(self, text):
        if re.search(r'\[P\d+\]', text):
            return [self.tra("占位符残留")]
        return []

    def _rule_check_number(self, text):
        if re.search(r'\d+\.\d+\.', text):
            return [self.tra("数字序号残留")]
        return []

    def _rule_check_example(self, text):
        if re.search(r'示例文本[A-Z]-\d+', text):
            return [self.tra("示例文本复读")]
        return []

    def _rule_check_newline(self, src, dst):
        s_n = src.strip().count('\n') + src.strip().count('\\n')
        d_n = dst.strip().count('\n') + dst.strip().count('\\n')
        if s_n != d_n:
            return [self.tra("换行符错误")]
        return []

    # 辅助方法
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


    def _analyze_file_in_chunks(self, cache_file, check_target: str, target_language_code: str, flag_key: str) -> Dict[str, Any] | None:
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

                    for line_info in mismatched_lines:
                        # 从行号获取在 cache_file.items中的索引
                        item_index = line_info['original_line_num'] - 1
                        item_to_flag = cache_file.items[item_index]

                        # 确保 extra 字典存在
                        if item_to_flag.extra is None:
                            item_to_flag.extra = {}

                        # 添加标记
                        item_to_flag.extra[flag_key] = True
                        self.debug(f"Flagged item at index {item_index} in file {cache_file.storage_path} with key '{flag_key}'")

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