from dataclasses import dataclass, field
from functools import cache
from typing import Any, ClassVar

import tiktoken

from ModuleFolders.Cache.BaseCache import ExtraMixin, ThreadSafeCache


class Status():

    UNTRANSLATED = 0        # 待翻译
    TRANSLATED = 1          # 已翻译
    TRANSLATING = 2         # 翻译中（弃用）
    EXCLUED = 7             # 已排除


@dataclass(repr=False)
class CacheItem(ThreadSafeCache, ExtraMixin):
    text_index: int = 0
    translation_status: int = 0
    model: str = ''
    source_text: str = ''
    translated_text: str = None
    extra: dict[str, Any] = field(default_factory=dict)
    """额外属性，用于存储特定reader产生的原文片段的额外属性，共用属性请加到CacheItem中"""

    def __post_init__(self):
        if self.translated_text is None:
            self.translated_text = self.source_text or ""
        super().__post_init__()

    @property
    def token_count(self):
        return self.get_token_count(self.source_text)

    @classmethod
    @cache
    def get_token_count(cls, text) -> int:
        return len(tiktoken.get_encoding("cl100k_base").encode(text))

    STATUS: ClassVar[Status] = Status
