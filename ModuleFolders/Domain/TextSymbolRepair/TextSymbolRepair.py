import re

from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig


class TextSymbolRepair:
    """规则驱动的文本符号修复引擎。

    核心思路（对应「原作符号不遵守，自动修复略无用」问题）：
    1. 先屏蔽 URL / Markdown 链接 / 占位标签 / HTML 标签等「不可触碰」片段，
       避免全局替换破坏它们（如 URL 中的 `?` 被改成 `？` 的历史问题）。
    2. 所有标点替换均为「条件替换」：仅当原文确实使用了对应符号时，
       才把译文中出现的替代符号还原为原文符号。
    3. 成对引号（「」『』“”‘’）支持首尾包裹与内部成对两种还原。
    4. 原文完全没有括号时，删除译文中「括号及括号内文本」——AI 额外添加的批注
       （如（译者注：…）、【补充说明】等），防止无中生有。
    """

    # 需要整体屏蔽、不做任何修改的片段
    # URL 主体排除 ()[]! 等字符（避免历史贪婪匹配问题），但允许紧跟一个平衡的
    # 括号尾段，如 https://a.jp/item(a)，保证「原文无括号」判断不被 URL 内的括号干扰
    _PROTECT_PATTERNS = [
        re.compile(r"https?://[^\s<>\"'()\[\]!，。！？；：、）】」』…]+(?:\([^()\s]*\))?"),
        re.compile(r"www\.[^\s<>\"'()\[\]!，。！？；：、）】」』…]+(?:\([^()\s]*\))?"),
        re.compile(r"\[[^\]]*\]\([^)]*\)"),   # Markdown 链接 [text](url)
        re.compile(r"<[^>]+>"),                # HTML / XML 标签
        re.compile(r"\[P\d+\]"),               # 占位符 [P0]
        re.compile(r"\{[^{}]*\}"),             # 花括号占位 {0}
    ]

    def repair_response_dict(self, config: TaskConfig, response_dict: dict[str, str]) -> dict[str, str]:
        if self._is_enabled(config) == False:
            return response_dict

        return response_dict.copy()

    def repair_text(self, config: TaskConfig, original_text: str, translated_text: str) -> str:
        if self._is_enabled(config) == False:
            return translated_text

        return self.repair_text_symbols(original_text, translated_text)

    def _is_enabled(self, config: TaskConfig) -> bool:
        return bool(getattr(config, 'text_symbol_repair_switch', False))

    # ============================================================
    # 保护段屏蔽 / 还原
    # ============================================================
    def _mask_protected(self, text: str) -> tuple[str, dict[str, str]]:
        """将受保护片段替换为哨兵 token，返回 (屏蔽后文本, {token: 原文片段})。"""
        spans = []
        for pattern in self._PROTECT_PATTERNS:
            for match in pattern.finditer(text):
                spans.append(match.span())

        if not spans:
            return text, {}

        spans.sort()
        merged = []
        for start, end in spans:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        tokens = {}
        result_parts = []
        cursor = 0
        for index, (start, end) in enumerate(merged):
            result_parts.append(text[cursor:start])
            token = f"\x00PROTECTED{index}\x01"
            result_parts.append(token)
            tokens[token] = text[start:end]
            cursor = end
        result_parts.append(text[cursor:])

        return "".join(result_parts), tokens

    def _unmask(self, text: str, tokens: dict[str, str]) -> str:
        for token, original in tokens.items():
            text = text.replace(token, original)
        return text

    # ============================================================
    # 主入口
    # ============================================================
    def repair_text_symbols(self, original_text: str, translated_text: str) -> str:
        """
        修复译文中的文本符号，分阶段处理首尾和内部标点。

        Args:
            original_text: 原始文本字符串。
            translated_text: 需要修复排版的译文文本字符串。

        Returns:
            修复文本符号后的译文文本字符串。
        """
        if not isinstance(original_text, str) or not isinstance(translated_text, str):
            return translated_text

        # --- 阶段 0: 处理前后缀空白 ---
        leading_whitespace_match = re.match(r"^(\s*)", original_text)
        trailing_whitespace_match = re.search(r"(\s*)$", original_text)
        leading_whitespace = leading_whitespace_match.group(1) if leading_whitespace_match else ""
        trailing_whitespace = trailing_whitespace_match.group(1) if trailing_whitespace_match else ""

        # 处理原文与译文的首尾空白
        original_stripped = original_text.strip()
        translated_stripped = translated_text.strip()

        # 如果原文或译文为空，则直接返回译文
        if not original_stripped or not translated_stripped:
            return translated_text

        # --- 屏蔽受保护片段（URL / 标签 / 占位符等），修复完成后还原 ---
        translated_masked, protected_tokens = self._mask_protected(translated_stripped)

        # 原文同样屏蔽一次：判断「原文是否含有括号」时忽略 URL 等受保护片段内的括号
        original_masked, _ = self._mask_protected(original_stripped)

        # --- 阶段 1: 引号还原（无中生有删除 / 位置对齐 / 单边补全） ---
        translated_masked = self._repair_quotes(original_stripped, translated_masked)

        # --- 阶段 1.5: 批注删除（原文无括号时，删除译文中的括号及括号内文本） ---
        translated_masked = self._repair_annotations(original_masked, translated_masked)

        # --- 阶段 2: 条件标点替换（仅当原文使用对应符号时才替换） ---
        translated_masked = self._repair_conditional_punctuation(original_stripped, translated_masked)

        # --- 还原受保护片段 ---
        translated_stripped = self._unmask(translated_masked, protected_tokens)

        # --- 阶段 3: 针对多行文本的双引号处理 ---
        _, translated_stripped = self.check_and_adjust_quotes(original_stripped, translated_stripped)

        # --- 最终处理: 还原前后空白 ---
        result = leading_whitespace + translated_stripped + trailing_whitespace
        return result

    # ============================================================
    # 成对引号
    # ============================================================
    # 成对型标点检查映射
    # 格式: (原文开始符, 原文结束符, [译文可能替代开始符], [译文可能替代结束符])
    _BOUNDARY_PUNCTUATION_PAIRS = [
        ('「', '」', ['“', '‘', '"'], ['”', '’', '"']),
        ('『', '』', ['“', '‘', '"'], ['”', '’', '"']),
        ('“', '”', ['‘', '「', '"'], ['’', '」', '"']),
        ('‘', '’', ['“', '「', '"'], ['”', '」', '"']),
    ]

    # 参与位置对齐的全部引号字符（不含撇号 '，避免误伤 don't 等）
    _QUOTE_CHARS = set('「」『』“”‘’"')

    # 「无中生有」删除集：原文完全没有引号时，删除译文中凭空出现的引号
    _STRIP_QUOTES = set('「」『』“”‘’"')

    # 批注括号对：原文完全没有括号时，删除译文中「括号及括号内文本」
    # （AI 额外添加的批注，如（译者注：…）、【补充说明】等）
    # 不含《》〈〉（书名号/角括号，可能是译文有意引用的标题），也不含 [] {}
    # （占位符 [P1] / 花括号 {0} 等由屏蔽阶段保护，[] 可能出现在游戏标签等合法内容中）
    _BRACKET_PAIRS = [
        ("（", "）"),
        ("【", "】"),
        ("〔", "〕"),
        ("〖", "〗"),
        ("(", ")"),
    ]
    _BRACKET_OPENERS = {pair[0] for pair in _BRACKET_PAIRS}
    _BRACKET_CLOSERS = {pair[1] for pair in _BRACKET_PAIRS}
    _BRACKET_ALL = _BRACKET_OPENERS | _BRACKET_CLOSERS

    def _repair_quotes(self, original: str, translated: str) -> str:
        """
        统一引号修复入口，按优先级处理三类问题：
        1. 无中生有：原文没有任何引号，译文却凭空出现引号 → 删除
        2. 位置对齐：原文与译文引号数量一致 → 按出现顺序一一还原（支持嵌套）
        3. 单边补全：原文首尾成对、译文只保留了一边 → 补全成对
        """
        # 1) 无中生有：原文完全没有引号 → 删除译文中凭空出现的引号
        if not any(char in self._STRIP_QUOTES for char in original):
            return self._strip_invented_quotes(translated)

        # 2) 位置对齐：原文/译文引号数量一致 → 按位置一一还原
        aligned = self._align_quote_positions(original, translated)
        if aligned is not None:
            return aligned

        # 3) 单边补全：原文首尾成对、译文只保留了一边 → 补全成对
        completed = self._complete_single_sided_quote(original, translated)
        if completed is not None:
            return completed

        return translated

    def _repair_annotations(self, original: str, translated: str) -> str:
        """删除译文中的「额外批注」。

        当原文完全没有括号时，译文里出现的括号及括号内文本视为 AI 额外添加的
        批注，整段删除（含括号本身）。支持同类型括号嵌套；孤立的不成对括号
        （只有左括号或只有右括号）也一并删除。
        """
        if any(char in self._BRACKET_ALL for char in original):
            return translated

        close_for = dict(self._BRACKET_PAIRS)
        result = []
        i = 0
        length = len(translated)
        while i < length:
            char = translated[i]
            if char in self._BRACKET_OPENERS:
                close = close_for[char]
                # 寻找配对闭合括号，支持同类型嵌套
                depth = 1
                j = i + 1
                while j < length:
                    current = translated[j]
                    if current == char:
                        depth += 1
                    elif current == close:
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                if depth == 0:
                    i = j + 1  # 删除整个括号段（含括号本身）
                    continue
                i += 1  # 孤立的左括号：删除
                continue
            if char in self._BRACKET_CLOSERS:
                i += 1  # 孤立的右括号：删除
                continue
            result.append(char)
            i += 1
        return "".join(result)

    def _strip_invented_quotes(self, translated: str) -> str:
        """删除译文中凭空出现的引号（原文没有引号时）。"""
        return "".join(char for char in translated if char not in self._STRIP_QUOTES)

    def _align_quote_positions(self, original: str, translated: str):
        """按出现顺序把译文的引号逐一还原为原文的引号。

        仅在原文与译文的引号数量完全一致时执行，支持嵌套引号（如「「」」）。
        数量不一致返回 None，交给其它规则处理。
        """
        orig_quotes = [char for char in original if char in self._QUOTE_CHARS]
        if not orig_quotes:
            return None

        trans_quotes = [char for char in translated if char in self._QUOTE_CHARS]
        if not trans_quotes or len(trans_quotes) != len(orig_quotes):
            return None

        result_parts = []
        quote_index = 0
        for char in translated:
            if char in self._QUOTE_CHARS:
                result_parts.append(orig_quotes[quote_index])
                quote_index += 1
            else:
                result_parts.append(char)
        return "".join(result_parts)

    def _complete_single_sided_quote(self, original: str, translated: str):
        """原文首尾成对（只此一对）、译文只保留了一边引号时，补全为原文引号对。

        例如原文 「こんにちは」，译文 “你好 或 你好” → 「你好」。
        """
        for orig_start, orig_end, alt_starts, alt_ends in self._BOUNDARY_PUNCTUATION_PAIRS:
            # 原文必须首尾成对且只有这一对
            if not (original.startswith(orig_start) and original.endswith(orig_end)):
                continue
            if original.count(orig_start) != 1 or original.count(orig_end) != 1:
                continue

            # 译文中的引号位置
            quote_positions = [(i, char) for i, char in enumerate(translated) if char in self._QUOTE_CHARS]

            # 只保留了一个引号时补全；没有引号时不凭空添加
            if len(quote_positions) != 1:
                continue

            pos, char = quote_positions[0]
            if pos == 0 and char in alt_starts:
                # 只有开头引号，缺结尾 → 补全
                inner = translated[len(char):]
                return orig_start + inner + orig_end

            if pos == len(translated) - len(char) and char in alt_ends:
                # 只有结尾引号，缺开头 → 补全
                inner = translated[:pos]
                return orig_start + inner + orig_end

        return None

    # ============================================================
    # 条件标点替换
    # ============================================================
    def _repair_conditional_punctuation(self, original: str, translated: str) -> str:
        """仅在原文使用了对应符号时，才把译文中出现的替代符号还原为原文符号。"""
        replacements = []  # (目标符号, [替代符号])，按目标符号长度降序处理

        if '？' in original:
            replacements.append(('？', ['?']))
        if '！' in original:
            replacements.append(('！', ['!']))
        if '……' in original:
            replacements.append(('……', ['......']))
        if '…' in original:
            replacements.append(('…', ['...', '。。。']))
        if '——' in original:
            replacements.append(('——', ['--']))
        elif '—' in original:
            replacements.append(('—', ['--']))

        # 先替换更长的目标符号，避免短目标先替换影响长目标匹配
        replacements.sort(key=lambda item: len(item[0]), reverse=True)

        for target, alternatives in replacements:
            for alt in alternatives:
                if alt in translated:
                    translated = translated.replace(alt, target)

        return translated

    # 处理多行文本的双引号问题，有些AI会在多行文本时，将每一行当作一句话进行翻译，导致每一行都加上了双引号
    def check_and_adjust_quotes(self, original, translation):
        # 分割原文和译文为行
        original_lines = original.split("\n")
        translation_lines = translation.split("\n")

        # 检查行数一致
        if len(original_lines) != len(translation_lines):
            return original, translation

        modified_translation = []

        for orig_line, trans_line in zip(original_lines, translation_lines):

            if len(trans_line) >= 2 and trans_line.startswith('"'):
                # 获取原文行首字符
                orig_start = orig_line[0] if len(orig_line) > 0 else ''

                # 如果原文首不符合要求，则去掉译文双引号
                if orig_start not in {'"', '“', '「', """'"""}:
                    trans_line = trans_line[1:]

            if len(trans_line) >= 2 and trans_line.endswith('"'):
                # 获取原文行尾字符
                orig_end = orig_line[-1] if len(orig_line) > 0 else ''

                # 如果原文尾不符合要求，则去掉译文双引号
                if orig_end not in {'"', '”', '」', """'"""}:
                    trans_line = trans_line[:-1]

            modified_translation.append(trans_line)

        # 重建译文文本
        adjusted_translation = '\n'.join(modified_translation)
        return original, adjusted_translation
