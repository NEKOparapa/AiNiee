import re
import regex
import regex._regex_core

class CharacterHelper:
    VALID_KEY = "is_valid"
    SEPARATOR_TOKEN = "[Separator]"
    DOT_SEPARATORS = r".．・·･∙⋅‧⸱﹒。｡"
    SPACE_SEPARATOR = " "
    
    @staticmethod
    def _normalize_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _parse_source_text(source_text: str):
        # 使用 regex 解析树区分纯字面量和真实正则
        return regex._regex_core._parse_pattern(
            regex._regex_core.Source(source_text),
            regex._regex_core.Info(),
        )

    @classmethod
    def _extract_literal_text(cls, node) -> str | None:
        # 只有完整还原为连续字符时，才视为普通术语。
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
    def is_regex_pattern(cls, source_text: str) -> bool:
        source_text = cls._normalize_text(source_text)
        if not source_text:
            return False
        
        try:
            regex.compile(source_text)
        except regex.error:
            return False

        literal_text = cls._get_literal_text(source_text)
        if literal_text is None:
            return True
        return literal_text != source_text

    @classmethod
    def _match_separator_at(cls, name: str, start: int) -> tuple[str, int] | None:
        if name.startswith(cls.SEPARATOR_TOKEN, start):
            return cls.SEPARATOR_TOKEN, len(cls.SEPARATOR_TOKEN)

        char = name[start]
        if char == cls.SPACE_SEPARATOR or char in cls.DOT_SEPARATORS:
            return char, 1

        return None

    @classmethod
    def _has_consecutive_separators(cls, name: str) -> bool:
        previous_is_separator = False
        index = 0
        while index < len(name):
            separator = cls._match_separator_at(name, index)
            if separator:
                if previous_is_separator:
                    return True
                previous_is_separator = True
                index += separator[1]
                continue

            previous_is_separator = False
            index += 1

        return False

    @classmethod
    def _parse_name(cls, original_name: str) -> tuple[list[str], list[str]]:
        parts = []
        separators = []
        current_part = []
        index = 0

        while index < len(original_name):
            separator = cls._match_separator_at(original_name, index)
            if separator:
                parts.append("".join(current_part).strip())
                separators.append(separator[0])
                current_part = []
                index += separator[1]
                continue

            current_part.append(original_name[index])
            index += 1

        parts.append("".join(current_part).strip())
        return parts, separators

    @classmethod
    def _match_separator_pattern(cls, allow_empty: bool) -> str:
        token_pattern = re.escape(cls.SEPARATOR_TOKEN)
        char_pattern = f"[ {re.escape(cls.DOT_SEPARATORS)}]"
        separator_pattern = f"(?:{token_pattern}|{char_pattern})"
        return f"{separator_pattern}?" if allow_empty else separator_pattern

    @classmethod
    def _display_separator(cls, separator: str) -> str:
        return "" if separator == cls.SEPARATOR_TOKEN else separator

    @classmethod
    def _build_display_name(cls, original_name: str, matched_parts: list[str] | None = None) -> str:
        parts, separators = cls._parse_name(original_name)
        matched_parts = matched_parts or []
        display_name = ""

        for index, part in enumerate(parts):
            if part:
                display_name += matched_parts[index] if index < len(matched_parts) else part
            if index < len(separators):
                display_name += cls._display_separator(separators[index])

        return display_name

    @classmethod
    def _build_full_name_match_pattern(cls, original_name: str) -> str:
        parts, separators = cls._parse_name(original_name)
        parts = [part for part in parts if part]
        if not parts:
            return ""

        pattern = f"({re.escape(parts[0])})"
        for index, separator in enumerate(separators):
            if index + 1 >= len(parts):
                break

            pattern += cls._match_separator_pattern(separator == cls.SEPARATOR_TOKEN)
            pattern += f"({re.escape(parts[index + 1])})"

        return pattern

    @classmethod
    def validate_name(cls, name: str) -> bool:
        name = cls._normalize_text(name)
        if not name:
            return True

        if cls._has_consecutive_separators(name):
            return False
            
        # 允许的分隔符暂时替换为普通字符，以避免被误判为正则
        test_name = name.replace(cls.SEPARATOR_TOKEN, "X")
        test_name = test_name.replace(cls.SPACE_SEPARATOR, "X")
        for dot in cls.DOT_SEPARATORS:
            test_name = test_name.replace(dot, "X")
            
        # 检查是否有其它的正则特性
        if cls.is_regex_pattern(test_name):
            return False
            
        return True

    @classmethod
    def normalize_row(cls, row: dict) -> dict:
        # 持久化校验结果，UI 与任务流程复用同一份有效性判断。
        normalized_row = dict(row) if isinstance(row, dict) else {}
        name = cls._normalize_text(normalized_row.get("original_name", ""))
        normalized_row["original_name"] = name
        # 补充其它的字段，确保一致性
        for key in ["translated_name", "gender", "age", "personality", "speech_style", "additional_info"]:
            normalized_row[key] = cls._normalize_text(normalized_row.get(key, ""))
            
        normalized_row[cls.VALID_KEY] = cls.validate_name(name)
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
    def split_name(cls, original_name: str) -> list[str]:
        if not original_name:
            return []

        parts, _ = cls._parse_name(original_name)
        return [part.strip() for part in parts if part.strip()]

    @classmethod
    def build_full_name_pattern(cls, original_name: str, keywords: list[str]) -> str:
        if not keywords:
            return ""

        parts, separators = cls._parse_name(original_name)
        parts = [part for part in parts if part]

        if len(parts) == 1:
            return re.escape(parts[0])

        pattern = re.escape(parts[0])
        for index, separator in enumerate(separators):
            if index + 1 >= len(parts):
                break
            pattern += cls._match_separator_pattern(separator == cls.SEPARATOR_TOKEN)
            pattern += re.escape(parts[index + 1])

        return pattern

    @classmethod
    def normalize_full_match(cls, original_name: str, matched_text: str) -> str:
        full_name_pattern = cls._build_full_name_match_pattern(original_name)
        if not full_name_pattern:
            return matched_text

        full_match = re.fullmatch(full_name_pattern, matched_text, re.IGNORECASE)
        if not full_match:
            return cls._build_display_name(original_name)

        return cls._build_display_name(original_name, list(full_match.groups()))

    @classmethod
    def match_original_name(cls, original_name: str, full_text: str, is_valid: bool = True) -> str | None:
        if not is_valid:
            return None
            
        keywords = cls.split_name(original_name)
        if not keywords or not full_text:
            return None

        full_name_pattern = cls._build_full_name_match_pattern(original_name)
        if full_name_pattern:
            full_match = re.search(full_name_pattern, full_text, re.IGNORECASE)
            if full_match:
                return cls._build_display_name(original_name, list(full_match.groups()))

        display_name = cls._build_display_name(original_name)
        is_matched = False
        for keyword in keywords:
            match = re.search(re.escape(keyword), full_text, re.IGNORECASE)
            if not match:
                continue

            is_matched = True
            actual_text = match.group()
            display_name = re.sub(
                re.escape(keyword),
                lambda _: actual_text,
                display_name,
                count=1,
                flags=re.IGNORECASE,
            )

        if is_matched:
            return display_name

        return None
