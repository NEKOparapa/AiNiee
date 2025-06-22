from dataclasses import dataclass, field
from functools import cache
from typing import Any

import tiktoken

from ModuleFolders.Cache.BaseCache import ExtraMixin, ThreadSafeCache


class TranslationStatus:
    UNTRANSLATED = 0  # 待翻译
    TRANSLATED = 1  # 已翻译
    POLISHED = 2  # 已润色
    EXCLUDED = 7  # 已排除


@dataclass(repr=False)
class CacheItem(ThreadSafeCache, ExtraMixin):
    text_index: int = 0
    translation_status: int = 0
    model: str = ''
    source_text: str = ''
    translated_text: str = None
    polished_text: str = None
    text_to_detect: str = None
    """处理后的待（语言）检测文本"""
    lang_code: tuple[str, float, list[str]] | None = None
    """当前行的语言代码 格式: [语言代码, 置信度, 除最高置信度外的语言代码列表]"""
    extra: dict[str, Any] = field(default_factory=dict)
    """额外属性，用于存储特定reader产生的原文片段的额外属性，共用属性请加到CacheItem中"""

    # 这里的赋值操作会自动调用下面的setter方法，行为保持不变
    def __post_init__(self):
        if self.source_text is None:
            self.source_text = ""

        if self.translated_text is None:
            self.translated_text = ""

        if self.polished_text is None:
            self.polished_text = ""


    @property
    def final_text(self) -> str:
        """
        获取最终文本。
        按以下优先级返回：
        1. 润色后的文本 (polished_text)
        2. 翻译后的文本 (translated_text)
        3. 原文 (source_text)
        """
        return self.polished_text or self.translated_text or self.source_text
    
    @property
    def token_count(self):
        return self.get_token_count(self.source_text)

    @classmethod
    @cache
    def get_token_count(cls, text) -> int:
        return len(tiktoken.get_encoding("cl100k_base").encode(text))

    def get_lang_code(self, default_lang=None):
        """获取语言代码，可选择使用默认值"""
        if self.lang_code is None and default_lang is not None:
            return (default_lang, 1.0, [])
        return self.lang_code

    def _extra(self) -> dict[str, Any]:
        return self.extra