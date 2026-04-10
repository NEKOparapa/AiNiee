import json
import os
import re
from typing import List, Dict, Any, Tuple

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.TranslationChecker.CheckResult import CheckResult


class RuleChecker(ConfigMixin, LogMixin, Base):
    def __init__(self, cache_manager: CacheManager):
        super().__init__()
        self.cache_manager = cache_manager
        self.config = self.load_config()

    def _summarize_text(self, text: str, limit: int = 24) -> str:
        normalized = re.sub(r'\s+', ' ', (text or "").strip())
        if not normalized:
            return "空"
        if len(normalized) <= limit:
            return normalized
        return normalized[:limit] + "..."

    def _build_rule_error(self, label: str, src_detail: str, dst_detail: str) -> str:
        return "{}(原文: {}, 译文: {})".format(
            label,
            self._summarize_text(src_detail),
            self._summarize_text(dst_detail),
        )

    def _build_missing_preserve_error(self, label: str, src_detail: str) -> str:
        return "{}(原文存在{}，没有正确保留)".format(
            label,
            self._summarize_text(src_detail),
        )

    def run_check(self, params: dict) -> Tuple[str, Any]:
        """
        规则检查入口，返回新的结果结构给UI使用
        """
        pre_check_result, pre_check_data = self._perform_pre_checks("rule")
        if pre_check_result is not None:
            return pre_check_result, pre_check_data

        rules = params.get("rules", {})
        issue_rows = self._check_rules(rules)
        enabled_rules = [key for key, enabled in rules.items() if enabled]

        return CheckResult.SUCCESS_RULE_RESULT, {
            "enabled_rules": enabled_rules,
            "issue_rows": issue_rows,
            "passed": not issue_rows,
        }

    # --- 规则检查主流程 ---
    def _check_rules(self, rules_config: dict) -> List[Dict]:
        if not any(rules_config.values()):
            return []

        self.info("开始执行规则检查...")
        errors_list = []

        # 准备正则表达式模式
        patterns = []
        if rules_config.get("auto_process"):
            patterns = self._prepare_regex_patterns(rules_config.get("exclusion", False))

        # 准备禁翻表数据
        exclusion_data = self.config.get("exclusion_list_data", []) if rules_config.get("exclusion") else []
        check_attr = "translated_text"

        for file_path, file_obj in self.cache_manager.project.files.items():
            file_name = os.path.basename(file_path)
            for item in file_obj.items:
                # 0. 总是跳过被显式排除 (TranslationStatus.EXCLUDED) 的条目
                if item.translation_status == TranslationStatus.EXCLUDED:
                    continue

                text_content = getattr(item, check_attr, "")
                current_errors = []

                # 1. 未翻译/漏翻检查
                if rules_config.get("untranslated"):
                    if item.translation_status < TranslationStatus.TRANSLATED or not text_content:
                        errors_list.append({
                            "row_id": f"{file_name} : {item.text_index + 1}",
                            "error_type": self._build_rule_error("条目未翻译/内容为空", item.source_text, text_content),
                            "source": item.source_text,
                            "check_text": text_content,
                            "file_path": file_path,
                            "text_index": item.text_index,
                            "target_field": check_attr
                        })
                        # 如果已确定未翻译，通常内容为空或无意义，跳过后续的内容检查
                        continue

                # 2. 跳过空文本 (如果内容为空且不是为了检查未翻译，则跳过后续正则检查)
                if not text_content or not item.source_text:
                    continue

                # 3. 禁翻表
                if rules_config.get("exclusion") and exclusion_data:
                    current_errors.extend(self._rule_check_exclusion(item.source_text, text_content, exclusion_data))
                # 4. 自动处理
                if rules_config.get("auto_process") and patterns:
                    current_errors.extend(self._rule_check_auto_process(item.source_text, text_content, patterns))
                # 5. 占位符
                if rules_config.get("placeholder"):
                    current_errors.extend(self._rule_check_placeholder(item.source_text, text_content))
                # 6. 数字序号
                if rules_config.get("number"):
                    current_errors.extend(self._rule_check_number(item.source_text, text_content))
                # 7. 示例复读
                if rules_config.get("example"):
                    current_errors.extend(self._rule_check_example(item.source_text, text_content))
                # 8. 换行符
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

        self.info("规则检查完成，发现 {} 个问题。".format(len(errors_list)))
        return errors_list

    # --- 规则检查辅助方法 ---
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
                            if not errs:
                                errs.append(self._build_missing_preserve_error("禁翻表错误", match.group(0)))
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
                        if not errs:
                            errs.append(self._build_missing_preserve_error("自动处理错误", match.group(0)))
                        break
            except: continue
        return errs

    def _rule_check_placeholder(self, src, dst):
        match = re.search(r'\[P\d+\]', dst)
        if match:
            return ["占位符残留({})".format(self._summarize_text(match.group(0)))]
        return []

    def _rule_check_number(self, src, dst):
        match = re.search(r'\d+\.\d+\.', dst)
        if match:
            return ["数字序号残留({})".format(self._summarize_text(match.group(0)))]
        return []

    def _rule_check_example(self, src, dst):
        match = re.search(r'示例文本[A-Z]-\d+', dst)
        if match:
            return ["示例文本复读({})".format(self._summarize_text(match.group(0)))]
        return []

    def _rule_check_newline(self, src, dst):
        s_n = src.strip().count('\n') + src.strip().count('\\n')
        d_n = dst.strip().count('\n') + dst.strip().count('\\n')
        if s_n != d_n:
            return ["换行符错误(原文: {}个换行, 译文: {}个换行)".format(s_n, d_n)]
        return []

    # 辅助方法
    def _perform_pre_checks(self, mode: str) -> Tuple[str | None, Dict]:
        """执行预检查，确保项目和缓存数据有效"""
        if not self.cache_manager.project or not self.cache_manager.project.files:
            self.error("检查失败，请检查项目文件夹缓存是否正常")
            return CheckResult.ERROR_CACHE, {}

        has_content = False
        check_target_attr = "translated_text"
        status_to_check = TranslationStatus.TRANSLATED

        # 检查是否存在至少一个需要被检查的有效文本项
        for item in self.cache_manager.project.items_iter():
            if item.translation_status >= status_to_check and getattr(item, check_target_attr, "").strip():
                has_content = True
                break

        if not has_content:
            self.error("检查失败，请先执行翻译流程")
            return CheckResult.ERROR_NO_TRANSLATION, {}

        return None, {}
