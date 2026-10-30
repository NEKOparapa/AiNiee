import re
from typing import Iterable


class RegexSwitchHelper:
    """正则开关表格的统一数据规范化与校验工具。"""

    REGEX_KEY = "regex"
    LEGACY_GLOSSARY_STATE_KEY = "src_state"
    _warned_invalid_re_patterns = set()

    @staticmethod
    def _normalize_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return False

    @classmethod
    def normalize_glossary_row(cls, row: dict) -> dict:
        normalized = dict(row) if isinstance(row, dict) else {}
        normalized["src"] = cls._normalize_text(normalized.get("src"))
        normalized["dst"] = cls._normalize_text(normalized.get("dst"))
        normalized["info"] = cls._normalize_text(normalized.get("info"))
        normalized[cls.REGEX_KEY] = cls._normalize_bool(normalized.get(cls.REGEX_KEY, False))
        normalized.pop(cls.LEGACY_GLOSSARY_STATE_KEY, None)
        return normalized

    @classmethod
    def normalize_glossary_rows(cls, rows: Iterable[dict] | None) -> list[dict]:
        if not isinstance(rows, (list, tuple)):
            return []
        return [cls.normalize_glossary_row(row) for row in rows if isinstance(row, dict)]

    @classmethod
    def _normalize_pattern_row(cls, row: dict, source_key: str, text_keys: tuple[str, ...]) -> dict:
        normalized = dict(row) if isinstance(row, dict) else {}
        raw_regex = normalized.get(cls.REGEX_KEY, False)

        # 旧格式把表达式本体保存在 regex 字符串中；迁移后移入首列并开启开关。
        if isinstance(raw_regex, str):
            legacy_pattern = raw_regex.strip()
            if legacy_pattern:
                normalized[source_key] = legacy_pattern
                regex_enabled = True
            else:
                regex_enabled = False
        else:
            regex_enabled = cls._normalize_bool(raw_regex)

        for key in text_keys:
            normalized[key] = cls._normalize_text(normalized.get(key))
        normalized[cls.REGEX_KEY] = regex_enabled
        return normalized

    @classmethod
    def normalize_exclusion_row(cls, row: dict) -> dict:
        return cls._normalize_pattern_row(row, "markers", ("markers", "info"))

    @classmethod
    def normalize_exclusion_rows(cls, rows: Iterable[dict] | None) -> list[dict]:
        if not isinstance(rows, (list, tuple)):
            return []
        return [cls.normalize_exclusion_row(row) for row in rows if isinstance(row, dict)]

    @classmethod
    def normalize_replacement_row(cls, row: dict) -> dict:
        return cls._normalize_pattern_row(row, "src", ("src", "dst"))

    @classmethod
    def normalize_replacement_rows(cls, rows: Iterable[dict] | None) -> list[dict]:
        if not isinstance(rows, (list, tuple)):
            return []
        return [cls.normalize_replacement_row(row) for row in rows if isinstance(row, dict)]

    @classmethod
    def normalize_config(cls, config: dict) -> bool:
        """就地迁移配置中的四张表，返回数据是否发生变化。"""
        if not isinstance(config, dict):
            return False

        changed = False
        normalizers = (
            ("prompt_dictionary_data", cls.normalize_glossary_rows),
            ("exclusion_list_data", cls.normalize_exclusion_rows),
            ("pre_translation_data", cls.normalize_replacement_rows),
            ("post_translation_data", cls.normalize_replacement_rows),
        )
        for key, normalizer in normalizers:
            if key not in config:
                continue
            normalized = normalizer(config.get(key))
            if normalized != config.get(key):
                config[key] = normalized
                changed = True
        return changed

    @classmethod
    def is_regex_enabled(cls, row: dict) -> bool:
        return isinstance(row, dict) and row.get(cls.REGEX_KEY) is True

    @classmethod
    def is_valid_re_pattern(cls, row: dict, source_key: str) -> bool:
        if not cls.is_regex_enabled(row):
            return True
        source = cls._normalize_text(row.get(source_key))
        if not source:
            return True
        try:
            re.compile(source)
            return True
        except re.error:
            return False

    @classmethod
    def build_re_pattern(cls, row: dict, source_key: str):
        """为禁翻类规则构造模式；无效或空规则返回 None。"""
        source = cls._normalize_text(row.get(source_key)) if isinstance(row, dict) else ""
        if not source:
            return None
        pattern_text = source if cls.is_regex_enabled(row) else re.escape(source)
        try:
            return re.compile(pattern_text)
        except re.error as error:
            cls.warn_invalid_re_pattern(source, error)
            return None

    @classmethod
    def warn_invalid_re_pattern(cls, source: str, error: Exception | None = None) -> None:
        source = cls._normalize_text(source)
        if not source or source in cls._warned_invalid_re_patterns:
            return
        detail = f": {error}" if error else ""
        print(f"[WARNING][RegexSwitchHelper] 跳过无效正则表达式 '{source}'{detail}")
        cls._warned_invalid_re_patterns.add(source)

    @classmethod
    def clear_warning_cache(cls) -> None:
        cls._warned_invalid_re_patterns.clear()
