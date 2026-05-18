import os
import re
from typing import Any, Dict, List, Tuple

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Domain.PromptBuilder.GlossaryHelper import GlossaryHelper
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.TranslationChecker.CheckResult import CheckResult


class TerminologyChecker(ConfigMixin, LogMixin, Base):
    def __init__(self, cache_manager: CacheManager):
        super().__init__()
        self.cache_manager = cache_manager
        self.config = self.load_config()

    def run_check(self, params: dict | None = None) -> Tuple[str, Any]:
        """
        术语检查入口，返回新的结果结构给 UI 使用
        """
        pre_check_result, pre_check_data = self._perform_pre_checks("terminology")
        if pre_check_result is not None:
            return pre_check_result, pre_check_data

        issue_rows = self._check_terminology()

        return CheckResult.SUCCESS_TERMINOLOGY_RESULT, {
            "issue_rows": issue_rows,
            "passed": not issue_rows,
        }

    def _normalize_identity(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _get_project_analysis_data(self) -> Dict[str, Any]:
        if not self.cache_manager or not hasattr(self.cache_manager, "get_analysis_data"):
            return {}

        analysis_data = self.cache_manager.get_analysis_data() or {}
        return analysis_data if isinstance(analysis_data, dict) else {}

    def _collect_merged_term_rows(self) -> List[Dict[str, str]]:
        merged_rows: List[Dict[str, str]] = []
        seen_sources = set()
        analysis_data = self._get_project_analysis_data()

        row_sources = (
            (analysis_data.get("characters", []), "source", "recommended_translation", "project"),
            (analysis_data.get("terms", []), "source", "recommended_translation", "project"),
            (GlossaryHelper.normalize_rows(self.config.get("prompt_dictionary_data", [])), "src", "dst", "glossary"),
        )

        for rows, source_field, target_field, row_type in row_sources:
            if not isinstance(rows, list):
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue

                if row_type == "glossary" and not GlossaryHelper.is_row_valid(row):
                    continue

                src_term = self._normalize_identity(row.get(source_field))
                dst_term = self._normalize_identity(row.get(target_field))
                if not src_term or not dst_term or src_term in seen_sources:
                    continue

                merged_rows.append({
                    "src": src_term,
                    "dst": dst_term,
                    "row_type": row_type,
                    GlossaryHelper.VALID_KEY: row.get(GlossaryHelper.VALID_KEY, GlossaryHelper.STATE_VALID),
                })
                seen_sources.add(src_term)

        return merged_rows

    def _prepare_term_data(self, term_rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        term_data = []

        for term in term_rows:
            src_term = term.get("src")
            dst_term = term.get("dst")
            if not src_term or not dst_term:
                continue

            if term.get("row_type") == "glossary":
                pattern = GlossaryHelper.build_search_pattern(
                    src_term,
                    term.get(GlossaryHelper.VALID_KEY),
                )
                if pattern is None:
                    continue

                term_data.append({
                    "type": "pattern",
                    "pattern": pattern,
                    "src": src_term,
                    "dst": dst_term,
                })
                continue

            try:
                pattern = re.compile(src_term, re.IGNORECASE)
                term_data.append({
                    "type": "pattern",
                    "pattern": pattern,
                    "src": src_term,
                    "dst": dst_term,
                })
            except re.error:
                term_data.append({
                    "type": "string",
                    "src": src_term,
                    "dst": dst_term,
                })

        return term_data

    # --- 术语检查主流程 ---
    def _check_terminology(self) -> List[Dict]:
        self.info("开始执行术语检查...")
        errors_list = []
        check_attr = "translated_text"

        term_rows = self._collect_merged_term_rows()
        term_data = self._prepare_term_data(term_rows)

        for file_path, file_obj in self.cache_manager.project.files.items():
            file_name = os.path.basename(file_path)
            for item in file_obj.items:
                # 始终跳过显式排除项
                if item.translation_status == TranslationStatus.EXCLUDED:
                    continue

                text_content = getattr(item, check_attr, "")

                if not text_content or not item.source_text:
                    continue

                current_errors = self._rule_check_terminology(item.source_text, text_content, term_data)

                for err in current_errors:
                    errors_list.append({
                        "row_id": f"{file_name} : {item.text_index + 1}",
                        "error_type": err,
                        "source": item.source_text,
                        "check_text": text_content,
                        "file_path": file_path,
                        "text_index": item.text_index,
                        "target_field": check_attr,
                    })

        self.info("术语检查完成，发现 {} 个问题。".format(len(errors_list)))
        return errors_list

    # --- 术语检查辅助方法 ---
    def _rule_check_terminology(self, src, dst, prepared_data):
        """
        检查术语一致性
        prepared_data: 包含预编译正则或字符串信息的列表
        """
        errs = []
        for term_item in prepared_data:
            match_found = False

            if term_item["type"] == "pattern":
                if term_item["pattern"].search(src):
                    match_found = True
            else:
                if term_item["src"].lower() in src.lower():
                    match_found = True

            if match_found:
                src_term = term_item["src"]
                dst_term = term_item["dst"]
                if dst_term not in dst:
                    err_msg = "术语缺失(原文: {}, 译文: {})".format(src_term, dst_term)
                    if err_msg not in errs:
                        errs.append(err_msg)
        return errs

    # 辅助方法
    def _perform_pre_checks(self, mode: str) -> Tuple[str | None, Dict]:
        """执行预检查，确保项目和缓存数据有效"""
        if not self.cache_manager.project or not self.cache_manager.project.files:
            self.error("检查失败，请检查项目文件夹缓存是否正常")
            return CheckResult.ERROR_CACHE, {}

        has_content = False
        check_target_attr = "translated_text"
        status_to_check = TranslationStatus.TRANSLATED

        for item in self.cache_manager.project.items_iter():
            if item.translation_status >= status_to_check and getattr(item, check_target_attr, "").strip():
                has_content = True
                break

        if not has_content:
            self.error("检查失败，请先执行翻译流程")
            return CheckResult.ERROR_NO_TRANSLATION, {}

        return None, {}
