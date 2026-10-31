import os
from typing import Any, Dict, List, Tuple

from Backend.core.base import Base
from Backend.core.config import ConfigMixin
from Backend.domain.prompts.glossary_helper import GlossaryHelper
from Backend.domain.config.tables import TableConfigHelper
from Backend.core.log import LogMixin
from Backend.infrastructure.cache import CacheManager
from Backend.domain.models.cache_item import TranslationStatus
from Backend.application.checks.check_result import CheckResult


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

        issue_rows = self._check_terminology(params or {})

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

    def _get_match_options(self, params: dict | None = None) -> Dict[str, bool]:
        match_options = {
            "case_sensitive": bool(self.config.get("prompt_dictionary_match_case_sensitive", False)),
            "whole_word": bool(self.config.get("prompt_dictionary_match_whole_word", False)),
            "split_match": bool(self.config.get("prompt_dictionary_match_split", False)),
        }
        if not isinstance(params, dict):
            return match_options

        if "case_sensitive" in params:
            match_options["case_sensitive"] = bool(params.get("case_sensitive"))
        if "whole_word" in params:
            match_options["whole_word"] = bool(params.get("whole_word"))
        if "split_match" in params:
            match_options["split_match"] = bool(params.get("split_match"))

        return match_options

    def _collect_merged_term_rows(self) -> List[Dict[str, Any]]:
        merged_rows = []
        project_sources = set()
        analysis_data = self._get_project_analysis_data()

        for rows in (analysis_data.get("characters", []), analysis_data.get("terms", [])):
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                src = self._normalize_identity(row.get("source"))
                dst = self._normalize_identity(row.get("recommended_translation"))
                identity = (src, False)
                if not src or not dst or identity in project_sources:
                    continue
                merged_rows.append({"src": src, "dst": dst, "row_type": "project", "regex": False})
                project_sources.add(identity)

        for table in TableConfigHelper.get_tables(self.config, "prompt_dictionary", enabled_only=True):
            for row in table["rows"]:
                if not row.get("src"):
                    continue
                if GlossaryHelper.source_identity(row) in project_sources:
                    continue
                if not GlossaryHelper.is_row_valid(row):
                    continue
                merged_rows.append({
                    **row,
                    "row_type": "glossary",
                    "table_id": table["id"],
                    "match_options": table["match_options"],
                })
        return merged_rows

    def _prepare_term_data(
        self,
        term_rows: List[Dict[str, Any]],
        match_options: Dict[str, bool] | None = None,
    ) -> List[Dict[str, Any]]:
        term_data = []
        for term in term_rows:
            src_term = term.get("src")
            dst_term = term.get("dst", "")
            if not src_term:
                continue

            # 公共术语始终使用所属表的设置；校对弹窗参数只影响项目表。
            options = TableConfigHelper.normalize_match_options(term.get("match_options", match_options))
            literal_options = {key: options[key] for key in ("case_sensitive", "whole_word")}
            regex_enabled = term.get("row_type") == "glossary" and term.get(GlossaryHelper.REGEX_KEY) is True
            split_match = options["split_match"] and term.get("row_type") == "glossary" and not regex_enabled
            pattern = GlossaryHelper.build_search_pattern(src_term, regex_enabled, **literal_options)
            if pattern is None:
                continue

            prepared_term = {
                "type": "pattern",
                "pattern": pattern,
                "selection_pattern": GlossaryHelper.build_search_pattern(
                    src_term, regex_enabled, split_match=split_match, **literal_options,
                ),
                "src": src_term,
                "dst": dst_term,
                "regex": regex_enabled,
                "table_id": term.get("table_id"),
                "match_options": options,
                "split_terms": [],
            }
            term_data.append(prepared_term)
            if not split_match:
                continue

            source_parts = GlossaryHelper.split_source_text(src_term)
            target_parts = GlossaryHelper.split_source_text(dst_term)
            # 无法按位置对应时仍参与优先级选择，但只验证完整译名。
            if len(source_parts) < 2 or len(source_parts) != len(target_parts):
                continue
            prepared_term["split_terms"] = [
                {
                    "pattern": GlossaryHelper.build_search_pattern(source_part, **literal_options),
                    "src": source_part,
                    "dst": target_part,
                }
                for source_part, target_part in zip(source_parts, target_parts)
            ]
        return term_data

    # --- 术语检查主流程 ---
    def _check_terminology(self, params: dict | None = None) -> List[Dict]:
        self.info("开始执行术语检查...")
        errors_list = []
        check_attr = "translated_text"

        term_rows = self._collect_merged_term_rows()
        term_data = self._prepare_term_data(term_rows, self._get_match_options(params))

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
        selected_terms = []
        claimed_sources = set()
        for term in prepared_data:
            identity = GlossaryHelper.source_identity(term)
            pattern = term.get("selection_pattern", term["pattern"])
            if identity in claimed_sources or not pattern.search(src):
                continue
            claimed_sources.add(identity)
            selected_terms.append(term)

        # 只让实际入选的表参与拆分歧义判断，低优先级译名不能干扰赢家。
        exact_translations = {}
        insensitive_translations = {}
        folded_translations = {}
        for term in selected_terms:
            if term.get("regex"):
                continue
            for part in [term, *term.get("split_terms", [])]:
                if not part["dst"]:
                    continue
                source = part["src"]
                folded = source.casefold()
                folded_translations.setdefault(folded, set()).add(part["dst"])
                if term["match_options"]["case_sensitive"]:
                    exact_translations.setdefault(source, set()).add(part["dst"])
                else:
                    insensitive_translations.setdefault(folded, set()).add(part["dst"])

        def is_unambiguous(part, options):
            source = part["src"]
            if options["case_sensitive"]:
                targets = exact_translations.get(source, set()) | insensitive_translations.get(source.casefold(), set())
            else:
                targets = folded_translations.get(source.casefold(), set())
            return len(targets) == 1

        errs = []
        for term in selected_terms:
            if term["pattern"].search(src):
                matched_terms = [term]
            else:
                matched_terms = [
                    part for part in term.get("split_terms", [])
                    if part["pattern"].search(src)
                    and is_unambiguous(part, term["match_options"])
                ]
            for matched_term in matched_terms:
                if matched_term["dst"] not in dst:
                    err_msg = "术语缺失(原文: {}, 译文: {})".format(matched_term["src"], matched_term["dst"])
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
