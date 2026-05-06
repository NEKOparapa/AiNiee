import re
import regex
import regex._regex_core

class CharacterHelper:
    VALID_KEY = "is_valid"
    DOT_SEPARATORS = r".．・·･∙⋅‧⸱﹒。｡"
    
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
    def validate_name(cls, name: str) -> bool:
        name = cls._normalize_text(name)
        if not name:
            return True
            
        # 允许的分隔符暂时替换为普通字符，以避免被误判为正则
        test_name = name.replace("[Separator]", "X")
        test_name = test_name.replace(" ", "X")
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

    @staticmethod
    def split_name(original_name: str) -> list[str]:
        if not original_name:
            return []

        if "[Separator]" in original_name:
            parts = original_name.split("[Separator]")
        elif " " in original_name or re.search(f"[{CharacterHelper.DOT_SEPARATORS}]", original_name):
            parts = re.split(f"[ {CharacterHelper.DOT_SEPARATORS}]+", original_name)
        else:
            parts = [original_name]

        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def build_full_name_pattern(original_name: str, keywords: list[str]) -> str:
        if not keywords:
            return ""

        if len(keywords) == 1:
            return re.escape(keywords[0])

        if "[Separator]" in original_name:
            separator_pattern = f"[ {CharacterHelper.DOT_SEPARATORS}]*"
        else:
            separator_pattern = f"[ {CharacterHelper.DOT_SEPARATORS}]+"

        return separator_pattern.join(re.escape(keyword) for keyword in keywords)

    @staticmethod
    def normalize_full_match(original_name: str, matched_text: str) -> str:
        if "[Separator]" not in original_name:
            return matched_text

        parts = re.split(f"[ {CharacterHelper.DOT_SEPARATORS}]+", matched_text)
        return "".join(part for part in parts if part)

    @classmethod
    def match_original_name(cls, original_name: str, full_text: str, is_valid: bool = True) -> str | None:
        if not is_valid:
            return None
            
        keywords = cls.split_name(original_name)
        if not keywords or not full_text:
            return None

        full_name_pattern = cls.build_full_name_pattern(original_name, keywords)
        if full_name_pattern:
            full_match = re.search(full_name_pattern, full_text, re.IGNORECASE)
            if full_match:
                return cls.normalize_full_match(original_name, full_match.group())

        display_name = original_name.replace("[Separator]", "")
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
