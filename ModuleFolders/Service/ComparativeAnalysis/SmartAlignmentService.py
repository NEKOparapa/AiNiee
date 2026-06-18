import concurrent.futures
from typing import List, Dict, Tuple
import rapidjson as json

from ModuleFolders.Base.Base import Base
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Infrastructure.LLMRequester.LLMClientFactory import LLMClientFactory
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester

class SmartAlignmentService(LogMixin, ConfigMixin, Base):
    """
    智能双语对齐服务
    负责将当前项目缓存中的原文 (CacheItems) 与导入的单语译文段落列表进行对齐。
    """
    def __init__(self, model_name: str, rpm_limit: int):
        super().__init__()
        self.model_name = model_name
        self.rpm_limit = rpm_limit

    def align(self, source_items: List[CacheItem], imported_texts: List[str]) -> List[Tuple[CacheItem, str]]:
        """
        核心对齐逻辑：
        如果数量完全一致，则直接 1:1 对齐（最优情况）。
        如果数量不一致，采用粗略相对位置映射。
        实际工程中可拓展为滑动窗口发给 LLM 纠正。
        """
        self.info(f"开始智能对齐，原文数量: {len(source_items)}, 导入译文数量: {len(imported_texts)}")
        
        # 1. 尝试直接长度对齐
        if len(source_items) == len(imported_texts):
            self.info("段落数量一致，采用 1:1 精确对齐。")
            return [(item, text) for item, text in zip(source_items, imported_texts)]

        # 2. 不一致时的回退策略：线性插值位置映射
        self.info("数量不一致，采用动态比例位置映射...")
        return self._align_by_ratio(source_items, imported_texts)

    def _align_by_ratio(self, source_items: List[CacheItem], imported_texts: List[str]) -> List[Tuple[CacheItem, str]]:
        results = []
        source_count = len(source_items)
        target_count = len(imported_texts)
        
        if source_count == 0 or target_count == 0:
            return []

        import math
        for i, item in enumerate(source_items):
            approx_idx = min(math.floor(i * (target_count / source_count)), target_count - 1)
            matched_text = imported_texts[approx_idx]
            results.append((item, matched_text))

        return results
