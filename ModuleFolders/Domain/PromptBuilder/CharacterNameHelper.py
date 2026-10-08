import re

from ModuleFolders.Domain.PromptBuilder.CharacterHelper import CharacterHelper


class CharacterNameHelper:
    """
    角色称呼变体（别名/敬称形式）扫描与路由辅助。

    以已确认的本名（全名）为锚点，在全项目原文中扫描该角色的实际出现形式：
    - 全名 / 名的单独出现
    - 全名 / 姓 / 名 + 常见敬称或称呼后缀（先輩、前辈、くん、さん、chan 等）

    用途：把这些称呼变体与对应本名一起注入翻译提示词，并附一致性指令，
    使模型对同一角色（含敬称）保持统一译名，避免"前辈/学姐"等译法混用。
    """

    # 常见敬称 / 称呼后缀（按出现场景覆盖日文、中文、英文习惯）。
    # 匹配时按词干后缀拼接，仅收集原文中真实出现的字符串，因此表宽不影响准确性。
    HONORIFIC_SUFFIXES = (
        # 日文习惯
        "先輩", "先辈", "前辈", "学姐", "学长", "师姐", "师兄",
        "くん", "君", "さん", "ちゃん", "様", "さま",
        "先生", "小姐", "同学", "老师", "大人", "桑", "酱",
        # 英文习惯
        "chan", "kun", "san", "sama", "senpai", "-chan", "-kun", "-san", "-sama",
    )

    # 变体去重时忽略的大小写差异
    _IGNORE_CASE = re.IGNORECASE

    @classmethod
    def _build_stems(cls, base_name: str) -> list[str]:
        """
        根据本名生成匹配词干（正则片段）。
        - 单部分名字：返回该名字本身。
        - 多部分名字（含 [Separator]、点、空格分隔）：返回"完整拼接"与"名（最后一部分）"两个词干，
          例如 远坂[Separator]凛 -> 远坂(?:分隔符)?凛 与 凛。
        """
        parts = CharacterHelper.split_name(base_name)
        if not parts:
            return []

        stems = []
        if len(parts) == 1:
            stems.append(re.escape(parts[0]))
        else:
            # 完整名：各部分之间允许出现一个常见的分隔符（点/空格/中点等）
            full_pattern = re.escape(parts[0])
            for part in parts[1:]:
                full_pattern += f"(?:[{re.escape(CharacterHelper.DOT_SEPARATORS + CharacterHelper.SPACE_SEPARATOR)}])?"
                full_pattern += re.escape(part)
            stems.append(full_pattern)
            # 名（最后一部分）常被单独用作称呼
            stems.append(re.escape(parts[-1]))

        return stems

    @classmethod
    def _scan_stem(cls, full_text: str, stem: str) -> set[str]:
        """扫描单个词干（可带可选敬称后缀）在全文中的实际出现形式。"""
        if not stem or not full_text:
            return set()

        suffix_pattern = "(?:" + "|".join(re.escape(s) for s in cls.HONORIFIC_SUFFIXES) + ")"
        # 词干与敬称之间允许至多一个空白，兼容 "Alice senpai" 这类英文习惯写法
        pattern = re.compile(stem + r"\s?" + suffix_pattern + "?", cls._IGNORE_CASE)
        found = set(match.group() for match in pattern.finditer(full_text))
        # 去掉纯空白形式
        return {text.strip() for text in found if text.strip()}

    @classmethod
    def collect_variants(cls, full_text: str, base_name: str) -> list[str]:
        """
        收集某个本名在全文中的称呼变体（不含本名本身）。

        Args:
            full_text: 全项目原文拼接文本。
            base_name: 已确认的本名 / 全名，支持 [Separator] 分隔姓与名。

        Returns:
            去重后的变体列表（保持扫描顺序）。
        """
        if not full_text or not base_name:
            return []

        stems = cls._build_stems(base_name)
        collected: set[str] = set()
        for stem in stems:
            collected.update(cls._scan_stem(full_text, stem))

        # 排除与本名完全一致的匹配（忽略大小写与空白差异）
        normalized_base = re.sub(r"\s+", "", base_name)
        variants = []
        for text in collected:
            normalized_text = re.sub(r"\s+", "", text)
            if normalized_text.lower() == normalized_base.lower():
                continue
            if text not in variants:
                variants.append(text)
        return variants

    @classmethod
    def collect_project_variants(cls, full_text: str, anchors: list[dict]) -> dict[str, list[str]]:
        """
        对一组本名锚点批量扫描变体。

        Args:
            full_text: 全项目原文拼接文本。
            anchors: 锚点行列表，每行需含 "source"（本名），可含 "recommended_translation"。

        Returns:
            {本名: [变体...]}，仅包含实际扫到变体的本名。
        """
        result: dict[str, list[str]] = {}
        if not full_text:
            return result

        for anchor in anchors or []:
            if not isinstance(anchor, dict):
                continue
            base_name = str(anchor.get("source", "") or "").strip()
            if not base_name:
                continue
            variants = cls.collect_variants(full_text, base_name)
            if variants:
                result[base_name] = variants
        return result
