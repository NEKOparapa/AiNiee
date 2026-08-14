import os
from typing import Any, Dict, List, Tuple

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Domain.TextSymbolRepair.TextSymbolRepair import TextSymbolRepair
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.TranslationChecker.CheckResult import CheckResult


class SymbolRepairChecker(ConfigMixin, LogMixin, Base):
    """符号修复检查器：按规则遍历项目全部已翻译条目，找出需要修复的译文。"""

    def __init__(self, cache_manager: CacheManager):
        super().__init__()
        self.cache_manager = cache_manager
        self.repairer = TextSymbolRepair()

    def run_repair(self, params: dict) -> Tuple[str, Any]:
        """执行符号修复扫描，返回与其它检查一致的结果结构。"""
        pre_check_result, pre_check_data = self._perform_pre_checks()
        if pre_check_result is not None:
            return pre_check_result, pre_check_data

        repair_rows = self._scan_repair_rows()
        return CheckResult.SUCCESS_SYMBOL_REPAIR_RESULT, {
            "repair_rows": repair_rows,
            "total_scanned": self._scanned_count,
        }

    # --- 主流程 ---
    def _scan_repair_rows(self) -> List[Dict]:
        self.info("开始执行符号修复扫描...")
        repair_rows = []
        self._scanned_count = 0

        for file_path, file_obj in self.cache_manager.project.files.items():
            file_name = os.path.basename(file_path)
            for item in file_obj.items:
                # 只处理已翻译 / 已润色的条目
                if item.translation_status < TranslationStatus.TRANSLATED:
                    continue

                source_text = item.source_text or ""
                translated_text = item.translated_text or ""
                if not source_text.strip() or not translated_text.strip():
                    continue

                self._scanned_count += 1
                repaired = self.repairer.repair_text_symbols(source_text, translated_text)
                if repaired != translated_text:
                    repair_rows.append({
                        "row_id": f"{file_name} : {item.text_index + 1}",
                        "row_number": item.text_index + 1,
                        "error_type": self.tra("符号修复"),
                        "source": source_text,
                        "check_text": repaired,
                        "before_text": translated_text,
                        "file_path": file_path,
                        "text_index": item.text_index,
                        "target_field": "translated_text",
                        "translation_status": item.translation_status,
                    })

        self.info("符号修复扫描完成，共 {} 条需要修复。".format(len(repair_rows)))
        return repair_rows

    # 辅助方法
    def _perform_pre_checks(self) -> Tuple[str | None, Dict]:
        """执行预检查，确保项目和缓存数据有效"""
        if not self.cache_manager.project or not self.cache_manager.project.files:
            self.error("修复失败，请检查项目文件夹缓存是否正常")
            return CheckResult.ERROR_CACHE, {}

        has_content = False
        for item in self.cache_manager.project.items_iter():
            if item.translation_status >= TranslationStatus.TRANSLATED and (item.translated_text or "").strip():
                has_content = True
                break

        if not has_content:
            self.error("修复失败，请先执行翻译流程")
            return CheckResult.ERROR_NO_TRANSLATION, {}

        return None, {}
