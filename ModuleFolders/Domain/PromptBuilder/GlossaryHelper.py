import regex
import regex._regex_core


class GlossaryHelper:
    VALID_KEY = "src_state"
    STATE_VALID = "valid"
    STATE_REGEX = "regex"
    STATE_INVALID = "invalid"

    @staticmethod
    def _normalize_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _compile_source_text(source_text: str):
        return regex.compile(source_text)

    @staticmethod
    def _parse_source_text(source_text: str):
        return regex._regex_core._parse_pattern(
            regex._regex_core.Source(source_text),
            regex._regex_core.Info(),
        )

    @classmethod
    def _extract_literal_text(cls, node) -> str | None:
        if isinstance(node, regex._regex_core.Sequence):
            literal_parts = []
            for item in node.items:
                literal_text = cls._extract_literal_text(item)
                if literal_text is None:
                    return None

                literal_parts.append(literal_text)

            return "".join(literal_parts)

        if isinstance(node, regex._regex_core.Character):
            if not node.positive or node.case_flags or node.zerowidth:
                return None

            try:
                return chr(node.value)
            except (TypeError, ValueError):
                return None

        return None

    @classmethod
    def _get_literal_text(cls, source_text: str) -> str | None:
        source_text = cls._normalize_text(source_text)
        if not source_text:
            return ""

        try:
            parsed_pattern = cls._parse_source_text(source_text)
        except Exception:
            return None

        return cls._extract_literal_text(parsed_pattern)

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
    def is_regex_pattern(cls, source_text: str) -> bool:
        source_text = cls._normalize_text(source_text)
        if not source_text:
            return False

        if not cls.validate_source_text(source_text):
            return False

        literal_text = cls._get_literal_text(source_text)
        if literal_text is None:
            return True

        return literal_text != source_text

    @classmethod
    def get_source_state(cls, source_text: str) -> str:
        source_text = cls._normalize_text(source_text)
        if not source_text:
            return cls.STATE_VALID

        if not cls.validate_source_text(source_text):
            return cls.STATE_INVALID

        if cls.is_regex_pattern(source_text):
            return cls.STATE_REGEX

        return cls.STATE_VALID

    @classmethod
    def is_row_valid(cls, row: dict) -> bool:
        if not isinstance(row, dict):
            return False

        return cls.get_row_state(row) != cls.STATE_INVALID

    @classmethod
    def is_row_regex(cls, row: dict) -> bool:
        if not isinstance(row, dict):
            return False

        return cls.get_row_state(row) == cls.STATE_REGEX

    @classmethod
    def get_row_state(cls, row: dict) -> str:
        if not isinstance(row, dict):
            return cls.STATE_INVALID

        stored = row.get(cls.VALID_KEY)
        if stored in (cls.STATE_VALID, cls.STATE_REGEX, cls.STATE_INVALID):
            return stored

        if isinstance(stored, bool):
            if stored:
                return cls.STATE_REGEX if cls.is_regex_pattern(row.get("src", "")) else cls.STATE_VALID
            return cls.STATE_INVALID

        return cls.get_source_state(row.get("src", ""))

    @classmethod
    def normalize_row(cls, row: dict) -> dict:
        normalized_row = dict(row) if isinstance(row, dict) else {}
        normalized_row["src"] = cls._normalize_text(normalized_row.get("src", ""))
        normalized_row["dst"] = cls._normalize_text(normalized_row.get("dst", ""))
        normalized_row["info"] = cls._normalize_text(normalized_row.get("info", ""))
        normalized_row[cls.VALID_KEY] = cls.get_source_state(normalized_row.get("src", ""))
        return normalized_row

    @classmethod
    def normalize_rows(cls, rows: list[dict] | None) -> list[dict]:
        normalized_rows = []

        if not isinstance(rows, list):
            return normalized_rows

        for row in rows:
            if not isinstance(row, dict):
                continue

            normalized_rows.append(cls.normalize_row(row))

        return normalized_rows

    @classmethod
    def build_search_pattern(cls, source_text: str, source_state: str | None = None):
        source_text = cls._normalize_text(source_text)
        if not source_text:
            return None

        if source_state is None:
            source_state = cls.get_source_state(source_text)

        if source_state == cls.STATE_INVALID:
            return None

        try:
            if source_state == cls.STATE_REGEX:
                return cls._compile_source_text(source_text)

            return regex.compile(regex.escape(source_text), regex.IGNORECASE)
        except regex.error:
            return None

    @classmethod
    def source_matches_text(cls, source_text: str, full_text: str, source_state: str | None = None) -> bool:
        pattern = cls.build_search_pattern(source_text, source_state)
        if pattern is None:
            return False

        return bool(pattern.search(full_text or ""))

    @classmethod
    def collect_matched_rows(
        cls,
        rows: list[dict] | None,
        input_dict: dict | None,
        include_invalid: bool = False,
    ) -> list[dict]:
        full_text = "\n".join(input_dict.values()) if isinstance(input_dict, dict) else ""
        if not full_text:
            return []

        matched_rows = []
        seen_keys = set()

        for row in cls.normalize_rows(rows):
            src = row.get("src", "")
            src_state = row.get(cls.VALID_KEY, cls.STATE_VALID)
            if not src:
                continue

            if src_state == cls.STATE_INVALID:
                if not include_invalid:
                    continue

                if src.lower() in full_text.lower():
                    dedupe_key = (src, row.get("dst", ""))
                    if dedupe_key in seen_keys:
                        continue

                    matched_rows.append(row.copy())
                    seen_keys.add(dedupe_key)
                continue

            pattern = cls.build_search_pattern(src, src_state)
            if pattern is None:
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
