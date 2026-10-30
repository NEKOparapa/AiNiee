from functools import lru_cache

import regex

from ModuleFolders.Domain.RegexSwitchHelper import RegexSwitchHelper
from ModuleFolders.Config.TableConfigHelper import TableConfigHelper


_CACHE_MAXSIZE = 8192


class GlossaryHelper:
    REGEX_KEY = RegexSwitchHelper.REGEX_KEY
    STATE_VALID = "valid"
    STATE_REGEX = "regex"
    STATE_INVALID = "invalid"
    _warned_invalid_sources = set()
    _split_pattern = regex.compile(r"[\s·・･∙⋅‧⸱]+")

    @staticmethod
    def _normalize_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    @lru_cache(maxsize=_CACHE_MAXSIZE)
    def _compile_source_text(source_text: str):
        return regex.compile(source_text)

    @classmethod
    def validate_source_text(cls, source_text: str) -> bool:
        source_text = cls._normalize_text(source_text)
        if not source_text:
            return True
        try:
            cls._compile_source_text(source_text)
            return True
        except regex.error:
            return False

    @classmethod
    def get_row_state(cls, row: dict) -> str:
        if not isinstance(row, dict):
            return cls.STATE_INVALID
        if not RegexSwitchHelper.is_regex_enabled(row):
            return cls.STATE_VALID
        if not cls.validate_source_text(row.get("src", "")):
            return cls.STATE_INVALID
        return cls.STATE_REGEX

    @classmethod
    def is_row_valid(cls, row: dict) -> bool:
        return cls.get_row_state(row) != cls.STATE_INVALID

    @classmethod
    def is_row_regex(cls, row: dict) -> bool:
        return cls.get_row_state(row) == cls.STATE_REGEX

    @classmethod
    def normalize_row(cls, row: dict) -> dict:
        return RegexSwitchHelper.normalize_glossary_row(row)

    @classmethod
    def normalize_rows(cls, rows: list[dict] | None) -> list[dict]:
        return RegexSwitchHelper.normalize_glossary_rows(rows)

    @classmethod
    def split_source_text(cls, source_text: str) -> list[str]:
        # 仅按显式分隔符拆分，保留 O'Connor、Mary-Jane 等名字内部的字符。
        return [part for part in cls._split_pattern.split(cls._normalize_text(source_text)) if part]

    @classmethod
    @lru_cache(maxsize=_CACHE_MAXSIZE)
    def build_search_pattern(
        cls,
        source_text: str,
        regex_enabled: bool = False,
        case_sensitive: bool = False,
        whole_word: bool = False,
        split_match: bool = False,
    ):
        source_text = cls._normalize_text(source_text)
        if not source_text:
            return None

        try:
            if regex_enabled is True:
                return cls._compile_source_text(source_text)

            pattern_text = regex.escape(source_text)
            if split_match:
                parts = cls.split_source_text(source_text)
                if len(parts) > 1:
                    # 完整原文优先；较长的部分优先，避免短词截断长词。
                    alternatives = [source_text, *sorted(dict.fromkeys(parts), key=len, reverse=True)]
                    pattern_text = "(?:" + "|".join(regex.escape(part) for part in alternatives) + ")"
            if whole_word:
                pattern_text = rf"(?<!\w){pattern_text}(?!\w)"

            flags = 0 if case_sensitive else regex.IGNORECASE
            return regex.compile(pattern_text, flags)
        except regex.error:
            return None

    @classmethod
    def source_matches_text(
        cls,
        source_text: str,
        full_text: str,
        regex_enabled: bool = False,
        case_sensitive: bool = False,
        whole_word: bool = False,
        split_match: bool = False,
    ) -> bool:
        pattern = cls.build_search_pattern(
            source_text,
            regex_enabled,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            split_match=split_match,
        )
        return bool(pattern and pattern.search(full_text or ""))

    @classmethod
    def collect_matched_rows(
        cls,
        rows: list[dict] | None,
        input_dict: dict | None,
        include_invalid: bool = False,
        case_sensitive: bool = False,
        whole_word: bool = False,
        split_match: bool = False,
    ) -> list[dict]:
        full_text = "\n".join(input_dict.values()) if isinstance(input_dict, dict) else ""
        if not full_text:
            return []

        matched_rows = []
        seen_keys = set()

        for row in cls.normalize_rows(rows):
            src = row.get("src", "")
            regex_enabled = row.get(cls.REGEX_KEY) is True
            if not src:
                continue

            if regex_enabled and not cls.validate_source_text(src):
                if src not in cls._warned_invalid_sources:
                    print(f"[WARNING][GlossaryHelper] 跳过无效术语正则表达式: '{src}'")
                    cls._warned_invalid_sources.add(src)
                continue

            pattern = cls.build_search_pattern(
                src,
                regex_enabled,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
                split_match=split_match,
            )
            if pattern is None:
                continue

            if split_match and not regex_enabled and len(cls.split_source_text(src)) > 1:
                # 部分命中只用于召回完整条目，不能把 John 配成整个姓名的译文。
                dedupe_key = (src, row.get("dst", ""))
                if dedupe_key not in seen_keys and pattern.search(full_text):
                    matched_rows.append(row.copy())
                    seen_keys.add(dedupe_key)
                continue

            found_texts = []
            seen_texts = set()
            for match in pattern.finditer(full_text):
                match_text = match.group(0)
                if not match_text or match_text in seen_texts:
                    continue
                found_texts.append(match_text)
                seen_texts.add(match_text)

            for match_text in found_texts:
                dedupe_key = (match_text, row.get("dst", ""))
                if dedupe_key in seen_keys:
                    continue
                new_row = row.copy()
                new_row["src"] = match_text
                matched_rows.append(new_row)
                seen_keys.add(dedupe_key)

        return matched_rows

    @classmethod
    def collect_matched_table_rows(cls, config, input_dict: dict | None) -> list[dict]:
        """按各表设置匹配；同源条目只采用最靠前且实际命中的表。"""
        matched_rows = []
        claimed_sources = set()
        seen_matches = set()
        for table in TableConfigHelper.get_tables(config, "prompt_dictionary", enabled_only=True):
            options = table["match_options"]
            rows = [
                {
                    **row,
                    "source_text": row.get("src", ""),
                    "table_id": table["id"],
                    "match_options": options,
                }
                for row in table["rows"]
            ]
            table_sources = set()
            for row in cls.collect_matched_rows(rows, input_dict, **options):
                source_key = cls.source_identity(row)
                if source_key in claimed_sources:
                    continue
                table_sources.add(source_key)
                match_key = (row["src"], row.get("dst", ""))
                if match_key not in seen_matches:
                    matched_rows.append(row)
                    seen_matches.add(match_key)
            # 同表内出现不同大小写的命中仍保留；优先级只作用于后面的表。
            claimed_sources.update(table_sources)
        return matched_rows

    @classmethod
    def source_identity(cls, row: dict) -> tuple[str, bool]:
        return (row.get("source_text", row.get("src", "")), row.get(cls.REGEX_KEY) is True)

    @classmethod
    def clear_cache(cls) -> None:
        cls._compile_source_text.cache_clear()
        cls.build_search_pattern.cache_clear()
        cls._warned_invalid_sources.clear()
