import os
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from ModuleFolders.Cache.BaseCache import ExtraMixin, ThreadSafeCache
from ModuleFolders.Cache.CacheItem import CacheItem


@dataclass(repr=False)
class CacheFile(ThreadSafeCache, ExtraMixin):
    """文件元数据"""

    storage_path: str = ""
    """文件相对路径"""

    encoding: str = "utf-8"
    """默认编码"""

    file_project_type: str = ""
    """文件项目类型"""

    line_ending: str = os.linesep
    """默认换行符"""

    items: list[CacheItem] = field(default_factory=list)
    """原文片段列表"""

    language_stats: list[tuple[str, int, float]] = field(default_factory=list)
    """检测到的语言次数与对应的平均置信度，可能有多种语言的存在"""

    lc_language_stats: list[tuple[str, int, float]] = field(default_factory=list)
    """检测到的低置信度的语言统计，主要在语言检测器中有用"""

    extra: dict[str, Any] = field(default_factory=dict)
    """额外属性，用于存储特定reader产生的文件的额外属性，共用属性请加到CacheFile中"""

    @property
    def file_name(self):
        return os.path.split(self.storage_path)[1]

    def add_item(self, item: CacheItem) -> None:
        """线程安全添加缓存项"""
        with self._lock:
            if hasattr(self, "items_dict"):
                del self.items_dict
            self.items.append(item)

    def get_item(self, text_index: int) -> CacheItem:
        """线程安全获取缓存项"""
        with self._lock:
            return self.items[self.items_index_dict[text_index]]

    @cached_property
    def items_index_dict(self):
        """item的全局唯一id对应当前file items里的下标"""
        return {v.text_index: i for i, v in enumerate(self.items)}

    def index_of(self, text_index):
        return self.items_index_dict[text_index]

    def _extra(self) -> dict[str, Any]:
        return self.extra
