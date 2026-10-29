"""Run the existing local quality checkers and adapt their results for any UI."""

from ModuleFolders.Application.ConfigService import ConfigService
from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.ItemService import ItemService
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Service.TranslationChecker.LanguageChecker import LanguageChecker
from ModuleFolders.Service.TranslationChecker.RuleChecker import RuleChecker
from ModuleFolders.Service.TranslationChecker.TerminologyChecker import TerminologyChecker


class CheckService:
    RULES = ("exclusion", "auto_process", "placeholder", "number", "example", "newline", "untranslated")
    CHECKERS = {"rule": RuleChecker, "language": LanguageChecker, "terminology": TerminologyChecker}

    def __init__(self, cache_manager):
        self.cache_manager = cache_manager
        self.config_service = ConfigService()

    def _parameters(self, kind, options):
        config = self.config_service.get_config()
        if kind == "rule":
            rules = options.get("rules") or {rule: config[f"rule_check_{rule}"] for rule in self.RULES}
            return {"rules": rules}, {f"rule_check_{rule}": enabled for rule, enabled in rules.items()}
        mapping = {
            "language": {"mode": "check_lang_mode_text", "chunk_size": "check_chunk_size", "threshold": "check_threshold_ratio", "exclude_non_translate": "check_exclude_non_translate"},
            "terminology": {"case_sensitive": "prompt_dictionary_match_case_sensitive", "whole_word": "prompt_dictionary_match_whole_word"},
        }[kind]
        params = {name: options.get(name, config[key]) for name, key in mapping.items()}
        return params, {mapping[name]: value for name, value in params.items()}

    def run_check(self, kind, options):
        if kind not in self.CHECKERS:
            raise ApplicationError("check_kind_invalid", 400)
        with exclusive_operation():
            with self.cache_manager.file_lock:
                project = self.cache_manager.project
            if project is None:
                raise ApplicationError("project_not_open", 409)
            params, saved_options = self._parameters(kind, options)
            self.config_service.patch_config(saved_options)
            checker = self.CHECKERS[kind](self.cache_manager)
            try:
                code, data = checker.run_check(params)
            except Exception as error:
                raise ApplicationError("check_failed", 500) from error
            finally:
                checker._cleanup_event_subscriptions()
            if code.startswith("ERROR"):
                raise ApplicationError({
                    "ERROR_CACHE": "check_cache_unavailable", "ERROR_NO_TRANSLATION": "check_no_translation",
                    "ERROR_INVALID_LANG": "check_language_invalid",
                }.get(code, "check_failed"), 400)
            issues = []
            for row in data.get("issue_rows", []):
                file, index = row["file_path"], row["text_index"]
                issues.append({
                    "id": ItemService.item_id(file, index), "file": file, "index": index,
                    "position": project.files[file].index_of(index),
                    "error": row.get("error_type", ""), "source": row.get("source", ""), "translation": row.get("check_text", ""),
                })
            result = {
                "kind": kind, "project_id": project.project_id, "passed": bool(data.get("passed", not issues)),
                "issues": issues, "reports": [{"file": row["file_path"], "project_type": row["file_type"], "encoding": row["encoding"], "stats": row["stats_text"]} for row in data.get("report_rows", [])],
                "target_language": data.get("target_language"), "mode": data.get("mode"),
            }
            # LanguageChecker also saves through the manager. Neither the
            # checker nor save_to_file may be called while holding file_lock.
            if kind == "language":
                try:
                    self.cache_manager.save_to_file()
                except OSError as error:
                    raise ApplicationError("item_save_failed", 500) from error
        event = {"rule": Base.EVENT.TABLE_RULE_CHECK_DONE, "language": Base.EVENT.TABLE_LANGUAGE_CHECK_DONE, "terminology": Base.EVENT.TABLE_TERMINOLOGY_CHECK_DONE}[kind]
        EventManager.get_singleton().emit(event, {"project_id": result["project_id"], "passed": result["passed"], "issue_count": len(issues)})
        return result
