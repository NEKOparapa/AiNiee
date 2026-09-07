import json
import re
from typing import List, Dict, Tuple, Any, Optional

from ModuleFolders.Config.FilePathConfig import regex_path
from ModuleFolders.Domain.RegexSwitchHelper import RegexSwitchHelper

class TextProcessor():
    # 定义日语字符集的正则表达式
    JAPANESE_CHAR_SET_CONTENT = (
        r'\u3040-\u309F'
        r'\u30A0-\u30FF'
        r'\u30FB-\u30FE'
        r'\uFF65-\uFF9F'
        r'\u4E00-\u9FFF'
        r'\u3400-\u4DBF'
        r'\uF900-\uFAFF'  # CJK兼容表意文字（如 豈），与LanguageFilter的is_cjk保持一致，否则被当作非日语affix漏发（audit #9）
        r'\u3001-\u303F'
        r'\uff01-\uff5e'
    )

    # 正则库路径
    DEFAULT_REGEX_DIR = regex_path("regex.json")

    # 数字序号与空白内容正则
    RE_DIGITAL_SEQ_PRE_STR = r'^(\d+)\.'
    RE_DIGITAL_SEQ_REC_STR = r'^【(\d+)】'
    RE_WHITESPACE_AFFIX_STR = r'^(\s*)(.*?)(\s*)$'

    # HTML换行标记（<br\b避免误伤<break>、<broom>等同前缀标签）
    RE_BR_TAG_STR = r'<br\b[^>]*>'

    def __init__(self, config: Any):
        super().__init__()

        # 数字序号预处理的已转换key记录（还原时只处理这些key，避免误改原文本就以【数字】开头的内容）
        self._digital_seq_keys: set = set()

        current_regex_dir = self.DEFAULT_REGEX_DIR

        # 预编译固定处理的正则表达式
        self.RE_DIGITAL_SEQ_PRE = re.compile(self.RE_DIGITAL_SEQ_PRE_STR)
        self.RE_DIGITAL_SEQ_REC = re.compile(self.RE_DIGITAL_SEQ_REC_STR)
        self.RE_BR_TAG = re.compile(self.RE_BR_TAG_STR, re.IGNORECASE)

        # 多行处理正则（使用MULTILINE标志）
        self.RE_WHITESPACE_AFFIX = re.compile(self.RE_WHITESPACE_AFFIX_STR, re.MULTILINE)

        # 日语字符处理正则
        ja_affix_pattern_str = (
            rf'(^[^{self.JAPANESE_CHAR_SET_CONTENT}]*)'  # Group 1: Prefix
            rf'(.*?)'  # Group 2: Core text
            rf'([^{self.JAPANESE_CHAR_SET_CONTENT}]*$)'  # Group 3: Suffix
        )
        self.RE_JA_AFFIX = re.compile(ja_affix_pattern_str, re.MULTILINE)

        # 预编译文本前后替换正则
        self.pre_translation_rules_compiled = self._compile_translation_rules(
            config.pre_translation_data
        )
        self.post_translation_rules_compiled = self._compile_translation_rules(
            config.post_translation_data
        )

        # 预编译自动处理正则
        code_pattern_strings = self._prepare_code_pattern_strings(
            config.exclusion_list_data, current_regex_dir
        )

        special_placeholder_pattern_strings = self._build_dynamic_pattern_strings(
            code_pattern_strings, r"\s*{p}\s*"
        )
        self.auto_compiled_patterns = [
            re.compile(p_str, re.IGNORECASE | re.MULTILINE)
            for p_str in special_placeholder_pattern_strings if p_str
        ]

    def _normalize_line_endings(self, text: str) -> Tuple[str, List[Tuple[int, str]]]:
        """
        统一换行符为 \n，并记录每个换行符的原始类型和位置
        现在支持HTML换行标记：<br>, <br/>, <br />
        返回: (标准化后的文本, 换行符位置和类型列表)
        """
        if not ('\r' in text or '\n' in text or '<br' in text.lower()):
            return text, []

        # 记录每个换行符的位置和类型
        line_endings = []
        normalized_text = ""
        i = 0
        line_pos = 0  # 在标准化文本中的行位置

        while i < len(text):
            # 检查HTML <br> 标记（不区分大小写，<br\b排除<break>等同前缀标签）
            br_match = self.RE_BR_TAG.match(text, i)
            if br_match:
                br_tag = br_match.group(0)
                line_endings.append((line_pos, br_tag))
                normalized_text += '\n'
                i = br_match.end()
                line_pos += 1
                continue

            # 检查传统换行符
            if i < len(text) - 1 and text[i:i + 2] == '\r\n':
                # Windows 换行符
                line_endings.append((line_pos, '\r\n'))
                normalized_text += '\n'
                i += 2
                line_pos += 1
            elif text[i] == '\r':
                # Mac 经典换行符
                line_endings.append((line_pos, '\r'))
                normalized_text += '\n'
                i += 1
                line_pos += 1
            elif text[i] == '\n':
                # Unix 换行符
                line_endings.append((line_pos, '\n'))
                normalized_text += '\n'
                i += 1
                line_pos += 1
            else:
                normalized_text += text[i]
                i += 1

        return normalized_text, line_endings

    def _restore_line_endings(self, text: str, line_endings: List[Tuple[int, str]]) -> str:
        """根据记录的换行符信息还原原始格式"""
        if not line_endings:
            return text

        lines = text.split('\n')
        if len(lines) <= 1:
            return text

        # 重建文本，使用对应的原始换行符
        result = []
        for i, line in enumerate(lines[:-1]):  # 最后一行后面没有换行符
            result.append(line)
            if i < len(line_endings):
                result.append(line_endings[i][1])
            else:
                result.append('\n')  # 默认使用 \n

        # 添加最后一行
        if lines:
            result.append(lines[-1])

        return ''.join(result)

    def _is_pure_english(self, text: str) -> bool:
        """
        判断文本是否为纯英文（仅包括英文字母和空格）
        排除纯空白的情况
        
        Args:
            text: 待检查的文本
            
        Returns:
            bool: 如果是纯英文返回True，否则返回False
        """
        if not text or not text.strip():
            return False
        
        # 只允许英文字母和空格
        return all((char.isalpha() and char.isascii()) or char.isspace() for char in text)

    def _handle_special_characters(self, prefix: str, core_text: str, suffix: str) -> Tuple[str, str, str]:
        """
        处理特殊字符边界
        包括：
        1. 括号等特殊字符的边界处理（移入核心文本）
        2. 纯数字后缀的处理（移入核心文本）
        3. 纯英文前后缀的还原（移入核心文本）
        
        Args:
            prefix: 前缀字符串
            core_text: 核心文本
            suffix: 后缀字符串
            
        Returns:
            处理后的 (prefix, core_text, suffix) 元组
        """
        # 处理前缀中的特殊字符
        if prefix:
            if prefix.endswith('['):
                core_text = '[' + core_text
                prefix = prefix[:-1]
            elif prefix.endswith('{'):
                core_text = '{' + core_text
                prefix = prefix[:-1]
            elif prefix.endswith('（'):
                core_text = '（' + core_text
                prefix = prefix[:-1]
            elif prefix.endswith('('):
                core_text = '(' + core_text
                prefix = prefix[:-1]

        # 处理后缀中的特殊字符
        if suffix:
            if suffix.startswith(']'):
                core_text = core_text + ']'
                suffix = suffix[1:]
            elif suffix.startswith('}'):
                core_text = core_text + '}'
                suffix = suffix[1:]
            elif suffix.startswith('）'):
                core_text = core_text + '）'
                suffix = suffix[1:]
            elif suffix.startswith(')'):
                core_text = core_text + ')'
                suffix = suffix[1:]

        # 数字后缀处理
        if suffix and suffix.isdigit():
            core_text = core_text + suffix
            suffix = ""

        # 检查前缀是否为纯英文，如果是则还原到核心文本
        if prefix and self._is_pure_english(prefix):
            core_text = prefix + core_text
            prefix = ""
        
        # 检查后缀是否为纯英文，如果是则还原到核心文本
        if suffix and self._is_pure_english(suffix):
            core_text = core_text + suffix
            suffix = ""

        return prefix, core_text, suffix

    def _process_multiline_text(self, text: str, use_ja_pattern: bool) -> Tuple[str, Dict]:
        """
        处理多行文本

        Args:
            text: 待处理文本
            use_ja_pattern: 是否使用日语模式（提取非日语字符作为前后缀）
        """
        # 统一换行符 - 总是执行
        normalized_text, line_endings = self._normalize_line_endings(text)

        # 按行分割
        lines = normalized_text.split('\n')

        # 选择正则模式：空白模式（默认）或日语模式
        pattern = self.RE_JA_AFFIX if use_ja_pattern else self.RE_WHITESPACE_AFFIX

        non_empty_lines = []  # 只存储非空行，用于翻译
        lines_info = []

        for line in lines:
            # 修改判断条件：检查空行或纯空白行
            if not line or not line.strip():  # 空行或纯空白行处理
                lines_info.append({
                    'prefix': '',
                    'suffix': '',
                    'is_empty': True,
                    'original_whitespace': line  # 保存原始空白字符
                })
                continue

            match = pattern.match(line)
            if match:
                prefix, core_text, suffix = match.group(1), match.group(2), match.group(3)

                # 应用特殊字符处理
                prefix, core_text, suffix = self._handle_special_characters(prefix, core_text, suffix)

                # 确保核心内容不为空
                if not core_text.strip() and line.strip():
                    core_text, prefix, suffix = line, '', ''

                # 检查前缀 (去除首尾空格后判断是否为数字)
                if prefix.strip().isdigit():
                    # 只保留前导空白作为前缀
                    prefix_leading = prefix[:len(prefix) - len(prefix.lstrip())]
                    core_text = prefix[len(prefix_leading):] + core_text  # 数字+紧邻空白都合并
                    prefix = prefix_leading

                # 检查后缀
                if suffix.strip().isdigit():
                    # 只保留后尾空白作为后缀
                    suffix_trailing = suffix[len(suffix.rstrip()):]
                    core_text = core_text + suffix[:len(suffix) - len(suffix_trailing)]  # 数字+紧邻空白都合并
                    suffix = suffix_trailing

                non_empty_lines.append(core_text)
                lines_info.append({'prefix': prefix, 'suffix': suffix, 'is_empty': False})
            else:
                non_empty_lines.append(line)
                lines_info.append({'prefix': '', 'suffix': '', 'is_empty': False})

        # 返回用于翻译的文本（不包含空行和纯空白行）
        processed_text = '\n'.join(non_empty_lines)

        return processed_text, {
            'type': 'multiline',
            'line_endings': line_endings,
            'lines_info': lines_info
        }

    def _create_empty_info(self) -> Dict:
        """创建空的处理信息"""
        return {
            'type': 'single',
            'line_ending': '\n',
            'lines_info': [{'prefix': '', 'suffix': '', 'is_empty': False}]
        }

    def _restore_multiline_text(self, text: str, info: Dict) -> str:
        """还原多行文本"""
        translated_lines = text.split('\n')
        lines_info = info.get('lines_info', [])
        line_endings = info.get('line_endings', [])

        # 验证翻译结果行数是否正确
        expected_translated_count = sum(1 for line_info in lines_info
                                        if not line_info.get('is_empty', False))

        if len(translated_lines) != expected_translated_count:
            print(f"[Warning]: 翻译前后行数不匹配! 期望{expected_translated_count}行，实际{len(translated_lines)}行")

        restored_lines = []
        translated_index = 0

        for line_info in lines_info:
            if line_info.get('is_empty', False):
                # 还原空行或纯空白行
                original_whitespace = line_info.get('original_whitespace', '')
                restored_lines.append(original_whitespace)
            else:
                # 还原非空行
                if translated_index < len(translated_lines):
                    line = translated_lines[translated_index]
                    prefix = line_info.get('prefix', '')
                    suffix = line_info.get('suffix', '')
                    restored_lines.append(f"{prefix}{line}{suffix}")
                    translated_index += 1
                else:
                    # 防护措施：如果翻译结果不够，使用空字符串
                    restored_lines.append('')

        # 还原原始换行符
        restored_text = '\n'.join(restored_lines)
        return self._restore_line_endings(restored_text, line_endings)

    def _compile_translation_rules(self, rules_data: Optional[List[Dict]]) -> List[Dict]:
        compiled_rules = []
        if not rules_data:
            return compiled_rules

        # 遍历文本替换的数据
        for rule in RegexSwitchHelper.normalize_replacement_rows(rules_data):
            new_rule = rule.copy()

            if RegexSwitchHelper.is_regex_enabled(rule):
                regex_str = rule.get("src", "")
                try:
                    new_rule["compiled_regex"] = re.compile(regex_str)
                except re.error as error:
                    RegexSwitchHelper.warn_invalid_re_pattern(regex_str, error)
                    continue

            compiled_rules.append(new_rule)
        return compiled_rules

    def _prepare_code_pattern_strings(self, exclusion_list_data: Optional[List[Dict]], regex_dir_path: str) -> List[str]:
        patterns: List[str] = []

        # 读取正则库内容
        with open(regex_dir_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            file_patterns = [item["regex"] for item in data
                             if isinstance(item, dict) and "regex" in item and item["regex"]]
        patterns.extend(file_patterns)

        # 读取禁翻表内容
        for item in RegexSwitchHelper.normalize_exclusion_rows(exclusion_list_data):
            pattern = RegexSwitchHelper.build_re_pattern(item, "markers")
            if pattern is not None:
                patterns.append(pattern.pattern)
        return patterns

    def _build_dynamic_pattern_strings(self, base_patterns: List[str], format_string: str) -> List[str]:
        """辅助函数，用于基于基础模式列表和格式化字符串构建增强的模式字符串(例如，在模式两侧添加空白匹配)"""
        enhanced_patterns = []
        if base_patterns:
            for p in base_patterns:
                if p:
                    try:
                        enhanced = format_string.format(p=p)
                        enhanced_patterns.append(enhanced)
                    except KeyError:
                        enhanced_patterns.append(p)
        return enhanced_patterns

    # 译前文本处理
    def replace_all(self, config, source_lang: str, text_dict: Dict[str, str]) -> \
            Tuple[Dict[str, str], Dict, Dict, Dict, Dict]:
        # 存储处理后信息的变量
        processed_text = {k: v for k, v in text_dict.items()}
        prefix_codes: Dict[str, List[Dict]] = {}
        suffix_codes: Dict[str, List[Dict]] = {}
        placeholder_order: Dict[str, List[Dict[str, str]]] = {}
        affix_whitespace_storage: Dict[str, Dict] = {}

        # 获取各个配置信息,减少再次传递
        pre_translation_switch = config.pre_translation_switch
        auto_process_text_code_segment = config.auto_process_text_code_segment
        target_platform = config.target_platform

        # 译前替换
        if pre_translation_switch:
            processed_text = self.replace_before_translation(processed_text)

        # 空白、换行、空行处理 - 总是执行（通用需求）
        # 非日语字符前后缀提取 - 仅当开关启用时生效
        processed_text, affix_whitespace_storage = self.strip_and_record_affixes(
            processed_text,
            source_lang,
            enable_non_ja_affix=auto_process_text_code_segment
        )

        # 代码段自动处理 - 根据开关决定
        if auto_process_text_code_segment:
            # 自动处理前后缀
            processed_text, prefix_codes, suffix_codes = self._process_affixes(
                processed_text,
                self.auto_compiled_patterns,
                self.auto_compiled_patterns
            )

            # 自动处理文本中间内容
            processed_text, placeholder_order = self._replace_special_placeholders(
                target_platform,
                processed_text,
                self.auto_compiled_patterns
            )

        # 处理数字序号
        processed_text = self.digital_sequence_preprocessing(processed_text)

        return processed_text, prefix_codes, suffix_codes, placeholder_order, affix_whitespace_storage

    # 译后文本处理
    def restore_all(self, config, text_dict: Dict[str, str], prefix_codes: Dict, suffix_codes: Dict,
                    placeholder_order: Dict, affix_whitespace_storage: Dict) -> Dict[str, str]:

        restored = text_dict.copy()

        # 获取各个配置信息
        auto_process_text_code_segment = config.auto_process_text_code_segment
        post_translation_switch = config.post_translation_switch

        # 代码段自动还原 - 根据开关决定
        if auto_process_text_code_segment:
            restored = self._restore_special_placeholders(restored, placeholder_order)
            restored = self._restore_affixes(restored, prefix_codes, suffix_codes)

        # 译后替换
        if post_translation_switch:
            restored = self.replace_after_translation(restored)

        # 数字序号还原
        restored = self.digital_sequence_recovery(restored)

        # 空白、换行还原 - 总是执行（与处理时保持一致）
        restored = self.restore_affix_whitespace(affix_whitespace_storage, restored)

        return restored

    # 处理并占位文本中间内容
    def _replace_special_placeholders(self, target_platform: str, text_dict: Dict[str, str],
                                    compiled_placeholder_patterns: List[re.Pattern]) -> \
            Tuple[Dict[str, str], Dict[str, List[Dict[str, str]]]]:
        new_dict = {}
        placeholder_order: Dict[str, List[Dict[str, str]]] = {}
        global_match_count = 0
        
        # 预编译系统占位符检测正则
        system_placeholder_pattern = re.compile(r'^\[P\d+\]$')
        sakura_placeholder_pattern = re.compile(r'^↓+$')

        for key, original_text in text_dict.items():
            current_text = original_text
            entry_placeholders: List[Dict[str, str]] = []
            sakura_match_count = 0

            for pattern_obj in compiled_placeholder_patterns:
                single_pattern_replacements: List[Dict[str, str]] = []

                def replacer_for_this_pattern(match_obj):
                    nonlocal global_match_count, sakura_match_count, single_pattern_replacements

                    if global_match_count >= 50:
                        return match_obj.group(0)

                    original_match_val = match_obj.group(0)
                    
                    # 检查是否匹配到系统占位符，如果是则跳过
                    if target_platform == "sakura":
                        # Sakura 模式下，检查是否全是 ↓ 字符
                        if sakura_placeholder_pattern.match(original_match_val):
                            return original_match_val  # 保持原样，不进行占位
                    else:
                        # 默认模式下，检查是否是 [P数字] 格式
                        if system_placeholder_pattern.match(original_match_val):
                            return original_match_val  # 保持原样，不进行占位

                    global_match_count += 1
                    sakura_match_count += 1

                    placeholder_val = f"[P{global_match_count}]"
                    if target_platform == "sakura":
                        placeholder_val = "↓" * sakura_match_count

                    # 避免与原文中真实存在的占位符字面量冲突（如游戏文本自带[P1]或↓）
                    while placeholder_val in current_text:
                        global_match_count += 1
                        sakura_match_count += 1
                        placeholder_val = f"[P{global_match_count}]" if target_platform != "sakura" else "↓" * sakura_match_count

                    single_pattern_replacements.append({
                        "placeholder": placeholder_val,
                        "original": original_match_val,
                        "pattern": pattern_obj.pattern
                    })
                    return placeholder_val

                try:
                    current_text = pattern_obj.sub(replacer_for_this_pattern, current_text)
                    entry_placeholders.extend(single_pattern_replacements)
                except Exception as e:
                    print(f"[Warning]: 占位正则替换出现问题！！ pattern '{pattern_obj.pattern}' on key '{key}': {e}")
                    continue

                if global_match_count >= 50:
                    break

            placeholder_order[key] = entry_placeholders
            new_dict[key] = current_text

        return new_dict, placeholder_order

    # 还原特殊占位符
    def _restore_special_placeholders(self, text_dict: Dict[str, str],
                                      placeholder_order: Dict[str, List[Dict[str, str]]]) -> Dict[str, str]:
        new_dic = {}
        for key, text in text_dict.items():
            placeholders_for_key = placeholder_order.get(key, [])

            if not placeholders_for_key:
                new_dic[key] = text
            else:
                restored_text = text
                for item in reversed(placeholders_for_key):
                    placeholder_text = item.get("placeholder")
                    original_text_val = item.get("original")
                    if placeholder_text is not None and original_text_val is not None:
                        if placeholder_text in restored_text:
                            restored_text = restored_text.replace(placeholder_text, original_text_val, 1)
                        else:
                            print(f"[Warning]: Placeholder '{placeholder_text}' not found in text for key '{key}' during restoration. Original: '{original_text_val}'")
                new_dic[key] = restored_text
        return new_dic

    # 处理前后缀
    def _process_affixes(self, text_dict: Dict[str, str], compiled_prefix_patterns: List[re.Pattern],
                         compiled_suffix_patterns: List[re.Pattern]) -> \
            Tuple[Dict[str, str], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
        prefix_codes: Dict[str, List[Dict]] = {}
        suffix_codes: Dict[str, List[Dict]] = {}
        processed_text_dict = {}

        for key, text_val in text_dict.items():
            current_text = text_val
            current_prefixes: List[Dict] = []
            current_suffixes: List[Dict] = []

            for pattern_obj in compiled_prefix_patterns:
                try:
                    while True:
                        match = pattern_obj.match(current_text)
                        # match.group(0)为空说明是零宽匹配，继续循环会死循环，按不匹配处理
                        if match and match.group(0):
                            prefix_text = match.group(0)
                            current_prefixes.append({"prefix": prefix_text, "pattern": pattern_obj.pattern})
                            current_text = current_text[len(prefix_text):]
                        else:
                            break
                except Exception as e:
                    print(f"[Warning]: 前缀正则匹配出现问题！！ Regex error for prefix pattern '{pattern_obj.pattern}' on key '{key}': {e}")
                    continue

            # 遍历预编译的后缀正则表达式
            for pattern_obj in compiled_suffix_patterns:
                try:
                    made_change = True
                    while made_change:
                        made_change = False
                        best_match = None
                        for match in pattern_obj.finditer(current_text):
                            if match.end() == len(current_text):
                                best_match = match
                        if best_match and best_match.group(0):
                            suffix_text = best_match.group(0)
                            current_suffixes.insert(0, {"suffix": suffix_text, "pattern": pattern_obj.pattern})
                            current_text = current_text[:best_match.start()]
                            made_change = True
                except Exception as e:
                    print(f"[Warning]: 后缀正则匹配出现问题！！ Regex error for suffix pattern '{pattern_obj.pattern}' on key '{key}': {e}")
                    continue

            # 特殊情况：如果移除前后缀后，中间的核心文本变为空白内容，还原最少内容的前后缀。
            if not current_text.strip():
                temp_prefix_str = ''.join([p['prefix'] for p in current_prefixes])
                temp_suffix_str = ''.join([s['suffix'] for s in current_suffixes])
                if current_prefixes and current_suffixes:
                    prefix_len = sum(len(p['prefix']) for p in current_prefixes)
                    suffix_len = sum(len(s['suffix']) for s in current_suffixes)
                    if prefix_len > suffix_len:
                        current_text = current_text + temp_suffix_str
                        current_suffixes = []
                    else:
                        current_text = temp_prefix_str + current_text
                        current_prefixes = []
                elif current_prefixes:
                    current_text = temp_prefix_str + current_text
                    current_prefixes = []
                elif current_suffixes:
                    current_text = current_text + temp_suffix_str
                    current_suffixes = []

            processed_text_dict[key] = current_text
            prefix_codes[key] = current_prefixes
            suffix_codes[key] = current_suffixes

        return processed_text_dict, prefix_codes, suffix_codes

    # 还原前后缀
    def _restore_affixes(self, text_dict: Dict[str, str], prefix_codes: Dict[str, List[Dict]],
                         suffix_codes: Dict[str, List[Dict]]) -> Dict[str, str]:
        restored_dict = {}
        for key, text in text_dict.items():
            # 按原始顺序拼接所有提取的前缀
            prefix_str = ''.join([item['prefix'] for item in prefix_codes.get(key, [])])
            # 按原始顺序拼接所有提取的后缀
            suffix_str = ''.join([item['suffix'] for item in suffix_codes.get(key, [])])
            restored_dict[key] = f"{prefix_str}{text}{suffix_str}"
        return restored_dict

    # 译前替换处理
    def replace_before_translation(self, text_dict: dict) -> dict:
        processed_text_dict = text_dict.copy()

        for k, original_text_val in processed_text_dict.items():
            current_text = original_text_val

            # 遍历所有预编译的译前规则
            for rule in self.pre_translation_rules_compiled:
                compiled_regex_obj = rule.get("compiled_regex")
                src_text = rule.get("src")
                dst_text = rule.get("dst", "")

                # 如果有已经编译好的正则
                if compiled_regex_obj:
                    try:
                        # 保持模板语义（支持\n、\1等合法用法），但dst含非法转义/无效组引用时
                        # 不再抛错终止任务，而是按字面量替换
                        current_text = compiled_regex_obj.sub(dst_text, current_text)
                    except re.error:
                        current_text = compiled_regex_obj.sub(lambda _m: dst_text, current_text)
                    continue

                # 没有正则，则按照原文替换
                elif src_text and src_text in current_text:
                    current_text = current_text.replace(src_text, dst_text)

            if current_text != original_text_val:
                processed_text_dict[k] = current_text

        return processed_text_dict

    # 译后替换处理
    def replace_after_translation(self, text_dict: dict) -> dict:
        processed_text_dict = text_dict.copy()

        for k, original_text_val in processed_text_dict.items():
            current_text = original_text_val

            # 遍历所有预编译的译后规则
            for rule in self.post_translation_rules_compiled:
                compiled_regex_obj = rule.get("compiled_regex")
                src_text = rule.get("src")
                dst_text = rule.get("dst", "")

                if compiled_regex_obj:
                    try:
                        # 保持模板语义，dst含非法转义/无效组引用时不再抛错，按字面量替换
                        current_text = compiled_regex_obj.sub(dst_text, current_text)
                    except re.error:
                        current_text = compiled_regex_obj.sub(lambda _m: dst_text, current_text)
                    continue

                elif src_text and src_text in current_text:
                    current_text = current_text.replace(src_text, dst_text)

            if current_text != original_text_val:
                processed_text_dict[k] = current_text

        return processed_text_dict

    # 处理数字序列
    def digital_sequence_preprocessing(self, text_dict: dict) -> dict:
        """
        遍历字典，仅当文本以 "数字." 格式开头时，将其替换为 "【数字】"。
        例如: "1. 这是标题" -> "【1】这是标题"
        同时记录被转换的key，还原时只处理这些key。
        """
        self._digital_seq_keys = set()
        for k in text_dict:
            # 使用新的正则表达式，它只匹配字符串开头的 "数字." 模式
            # r'【\1】' 移除了原来的点号
            new_text, count = self.RE_DIGITAL_SEQ_PRE.subn(r'【\1】', text_dict[k], count=1)
            if count:
                text_dict[k] = new_text
                self._digital_seq_keys.add(k)
        return text_dict

    # 还原数字序列
    def digital_sequence_recovery(self, text_dict: dict) -> dict:
        """
        遍历字典，仅当文本以 "【数字】" 格式开头时，将其还原为 "数字."。
        例如: "【1】这是标题" -> "1. 这是标题"
        只还原预处理阶段确实转换过的key，避免把原文本来就以【数字】开头的内容误改写。
        """
        for k in self._digital_seq_keys:
            if k in text_dict:
                # 使用新的正则表达式，它只匹配字符串开头的 "【数字】" 模式
                # r'\1.' 将捕获到的数字后面加上点号
                text_dict[k] = self.RE_DIGITAL_SEQ_REC.sub(r'\1.', text_dict[k], count=1)
        return text_dict

    # 处理前后缀的空格与换行，以及非日语文本（支持多行）
    def strip_and_record_affixes(self, text_dict: Dict[str, str], source_lang: str,
                                 enable_non_ja_affix: bool) -> Tuple[Dict[str, str], Dict[str, Dict]]:
        """
        处理文本的空白、换行和可选的非日语前后缀

        Args:
            text_dict: 待处理的文本字典
            source_lang: 源语言
            enable_non_ja_affix: 是否启用非日语字符前后缀处理（仅对日语生效）

        Returns:
            处理后的文本字典和处理信息

        说明：
            - 空白、换行、空行处理：总是执行（通用需求）
            - 非日语字符前后缀提取：根据 enable_non_ja_affix 参数决定
        """
        processed_text_dict: Dict[str, str] = {}
        processing_info: Dict[str, Dict] = {}

        for key, original_text in text_dict.items():
            # 检查是否是字符串
            if not isinstance(original_text, str):
                processed_text_dict[key] = original_text
                processing_info[key] = self._create_empty_info()
                continue

            # 根据配置决定是否使用日语模式
            use_ja_pattern = enable_non_ja_affix and (source_lang == 'ja' or source_lang == 'japanese')
            processed_text, info = self._process_multiline_text(original_text, use_ja_pattern)

            processed_text_dict[key] = processed_text
            processing_info[key] = info

        return processed_text_dict, processing_info

    # 还原前后缀的空格与换行（支持多行）
    def restore_affix_whitespace(self, processing_info: Dict[str, Dict], processed_dict: Dict[str, str]) -> Dict[str, str]:
        restored_text_dict: Dict[str, str] = {}

        for key, core_text in processed_dict.items():
            info = processing_info.get(key)
            if not info:
                restored_text_dict[key] = core_text
                continue

            # 使用多行还原逻辑
            restored_text = self._restore_multiline_text(core_text, info)
            restored_text_dict[key] = restored_text

        return restored_text_dict
