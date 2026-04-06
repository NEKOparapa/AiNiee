import os
import re
from typing import List, Dict, Any, Tuple

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
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
        术语检查入口，返回新的结果结构给UI使用
        """
        pre_check_result, pre_check_data = self._perform_pre_checks("terminology")
        if pre_check_result is not None:
            return pre_check_result, pre_check_data

        issue_rows = self._check_terminology()

        return CheckResult.SUCCESS_TERMINOLOGY_RESULT, {
            "issue_rows": issue_rows,
            "passed": not issue_rows,
        }

    # --- 术语检查主流程 ---
    def _check_terminology(self) -> List[Dict]:
        self.info(self.tra("开始执行术语检查..."))
        errors_list = []
        check_attr = "translated_text"

        # 准备术语表数据 (预处理正则)
        term_data = []
        raw_term_data = self.config.get("prompt_dictionary_data", [])
        for term in raw_term_data:
            if isinstance(term, dict):
                src_term = term.get("src")
                dst_term = term.get("dst")
                if src_term and dst_term:
                    try:
                        # 尝试编译为正则
                        pattern = re.compile(src_term, re.IGNORECASE)
                        term_data.append({
                            "type": "regex",
                            "pattern": pattern,
                            "src": src_term, # 保留原始字符串用于调试或显示
                            "dst": dst_term
                        })
                    except re.error:
                        # 编译失败则作为普通字符串处理，后续将使用忽略大小写包含检测
                        term_data.append({
                            "type": "string",
                            "src": src_term,
                            "dst": dst_term
                        })

        for file_path, file_obj in self.cache_manager.project.files.items():
            file_name = os.path.basename(file_path)
            for item in file_obj.items:
                # 总是跳过被显式排除 (TranslationStatus.EXCLUDED) 的条目
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
                        "target_field": check_attr
                    })

        self.info(self.tra("术语检查完成，发现 {} 个问题。").format(len(errors_list)))
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

            # 检测原文中是否存在该术语
            if term_item["type"] == "regex":
                if term_item["pattern"].search(src):
                    match_found = True
            else:
                # 字符串模式：使用忽略大小写包含，与PromptBuilder回退逻辑保持一致
                if term_item["src"].lower() in src.lower():
                    match_found = True

            # 如果原文中存在术语，则检查译文中是否包含对应的译名
            if match_found:
                dst_term = term_item["dst"]
                if dst_term not in dst:
                    err_msg = self.tra("术语缺失: {}").format(dst_term)
                    if err_msg not in errs:
                        errs.append(err_msg)
        return errs

    # 辅助方法
    def _perform_pre_checks(self, mode: str) -> Tuple[str | None, Dict]:
        """执行预检查，确保项目和缓存数据有效"""
        if not self.cache_manager.project or not self.cache_manager.project.files:
            self.error(self.tra("检查失败，请检查项目文件夹缓存是否正常"))
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
            self.error(self.tra("检查失败，请先执行翻译流程"))
            return CheckResult.ERROR_NO_TRANSLATION, {}

        return None, {}
