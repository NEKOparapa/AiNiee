import re
import functools # 导入 functools 用于 lru_cache
from typing import List, Dict, Tuple, Pattern # 增加 Pattern 类型导入

from Base.Base import Base


class TextProcessor(Base):
    # --- 预编译的类级别正则表达式 ---
    PRE_DIGIT_PATTERN = re.compile(r'^(\d+)\.')
    POST_DIGIT_PATTERN = re.compile(r'^【(\d+)】')
    AFFIX_PATTERN = re.compile(r'^(\s*)(.*?)(\s*)$', re.DOTALL)
    # --- 预编译 End ---

    # 修改构造函数，不再接收 code_pattern_list
    def __init__(self, config=None):
        super().__init__() # 调用父类的构造函数

        # --- 预编译译前/译后规则 ---
        # 从传入的 config 对象获取规则数据，如果 config 为 None 则使用空列表
        pre_data = getattr(config, 'pre_translation_data', []) if config else []
        post_data = getattr(config, 'post_translation_data', []) if config else []
        # 存储编译好的规则
        self.compiled_pre_rules = self._compile_translation_rules(pre_data)
        self.compiled_post_rules = self._compile_translation_rules(post_data)
        # --- 预编译 End ---

    @staticmethod
    @functools.lru_cache(maxsize=None) # 使用 lru_cache 缓存编译结果，避免重复编译相同模式
    def _compile_pattern_cached(pattern_str: str) -> Pattern | None:
        """编译单个正则表达式模式，处理可能的错误，并缓存结果"""
        try:
            if not pattern_str:
                return None
            return re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
        except re.error as e:
            # 暂时只打印，因为 Base.error 可能在此上下文不可用
            print(f"[Warning][TextProcessor]: 正则编译错误！！ pattern '{pattern_str}': {e}")
            return None

    def _compile_translation_rules(self, rules_data):
        """编译译前/译后替换规则中的正则表达式"""
        compiled_rules = []
        if not rules_data:
            return compiled_rules
        for rule in rules_data:
            if not isinstance(rule, dict):
                continue
            regex_pattern = rule.get("regex")
            compiled_pattern = None
            if regex_pattern:
                compiled_pattern = self._compile_pattern_cached(regex_pattern)
            compiled_rules.append({
                "compiled": compiled_pattern,
                "src": rule.get("src"),
                "dst": rule.get("dst", "")
            })
        return compiled_rules

    # 译前文本处理
    # <--- 修改签名，接收编译好的代码模式 -->
    def replace_all(self, config, text_dict: Dict[str, str], compiled_code_patterns_with_source: List[Tuple[str, re.Pattern]]) -> Tuple[Dict[str, str], Dict, Dict, Dict, Dict]:
        """执行全部替换操作"""
        processed_text = {k: v for k, v in text_dict.items()}
        prefix_codes, suffix_codes, placeholder_order = {}, {}, {}

        # 译前替换 (使用预编译规则)
        if config.pre_translation_switch:
            processed_text = self.replace_before_translation(config, processed_text)

        # 预处理文本前后的空格与换行
        processed_text, affix_whitespace_storage = self.strip_and_record_affix_whitespace(processed_text)

        # 自动处理代码段
        if config.auto_process_text_code_segment:
            # 处理前后缀 (使用预编译正则)
            # <--- 传递编译好的模式 -->
            processed_text, prefix_codes, suffix_codes = self._process_affixes(processed_text, compiled_code_patterns_with_source)

            # 特殊文本占位替换 (使用预编译正则)
            target_platform = getattr(config, 'target_platform', '') # 安全获取目标平台
            # <--- 传递编译好的模式 -->
            processed_text, placeholder_order = self._replace_special_placeholders(
                target_platform,
                processed_text,
                compiled_code_patterns_with_source
            )

        # 数字序号预处理
        processed_text = self.digital_sequence_preprocessing(processed_text)

        return processed_text, prefix_codes, suffix_codes, placeholder_order, affix_whitespace_storage

    # 译后文本处理
    def restore_all(self, config, text_dict: Dict[str, str], prefix_codes: Dict, suffix_codes: Dict, placeholder_order: Dict, affix_whitespace_storage: Dict) -> Dict[str, str]:
        """执行全部还原操作"""
        restored = text_dict.copy()

        # 自动处理代码段
        if config.auto_process_text_code_segment:
            # 占位符恢复 (逻辑不变)
            restored = self._restore_special_placeholders(restored, placeholder_order)
            # 前后缀恢复 (逻辑不变)
            restored = self._restore_affixes(restored, prefix_codes, suffix_codes)

        # 译后替换 (使用预编译规则)
        if config.post_translation_switch:
            restored = self.replace_after_translation(config, restored)

        # 数字序号恢复
        restored = self.digital_sequence_recovery(restored)

        # 前后缀的换行空格恢复
        restored = self.restore_affix_whitespace(affix_whitespace_storage, restored)

        return restored

    # <--- 修改签名，接收编译好的模式 -->
    def _replace_special_placeholders(self, target_platform: str, text_dict: Dict[str, str], compiled_patterns_with_source: List[Tuple[str, re.Pattern]]) -> Tuple[Dict[str, str], Dict[str, List[Dict[str, str]]]]:
        """特殊文本占位替换 (改进版，防止重复替换)"""
        new_dict = {}
        placeholder_order: Dict[str, List[Dict[str, str]]] = {}
        global_match_count = 0

        for key, original_text in text_dict.items():
            if not isinstance(original_text, str):
                new_dict[key] = original_text
                placeholder_order[key] = []
                continue

            current_text = original_text
            processed_spans = []
            entry_placeholders: List[Dict[str, str]] = []
            sakura_match_count = 0

            # 遍历预编译的模式对象
            for pattern_str, pattern in compiled_patterns_with_source: # <--- 使用元组解包
                replacements_in_this_pass = []

                try:
                    matches = list(pattern.finditer(current_text))
                except Exception as e:
                    self.error(f"查找匹配项时出错 (key: {key}, pattern: {pattern.pattern})", e)
                    continue

                for match in reversed(matches):
                    start, end = match.span()
                    is_overlapping = False
                    for p_start, p_end in processed_spans:
                        if (start >= p_start and end <= p_end) or \
                           (p_start >= start and p_end <= end) or \
                           (start < p_end and end > p_start):
                            is_overlapping = True
                            break
                    if is_overlapping:
                        continue

                    if global_match_count >= 50:
                         continue

                    global_match_count += 1
                    sakura_match_count += 1

                    original_match_text = match.group(0)

                    # 检查是否替换简单内容
                    if len(original_match_text) == 1 and not original_match_text.isalnum():
                        global_match_count -= 1
                        sakura_match_count -= 1
                        continue

                    if target_platform == "sakura":
                        placeholder = "↓" * sakura_match_count
                    else:
                        placeholder = f"[P{global_match_count}]"

                    replacements_in_this_pass.append({
                        "span": (start, end),
                        "placeholder": placeholder,
                        "original": original_match_text,
                        "pattern": pattern.pattern # 存储原始字符串 pattern_str
                    })
                    processed_spans.append((start, end))

                if replacements_in_this_pass:
                    replacements_in_this_pass.sort(key=lambda x: x["span"][0], reverse=True)
                    temp_text_list = list(current_text)
                    for rep_info in replacements_in_this_pass:
                        start, end = rep_info["span"]
                        temp_text_list[start:end] = list(rep_info["placeholder"])
                        # 添加到 entry_placeholders (按生成顺序，之后 restore 时 reversed)
                        entry_placeholders.append({
                            "placeholder": rep_info["placeholder"],
                            "original": rep_info["original"],
                            "pattern": rep_info["pattern"] # 使用 pattern_str
                        })
                    current_text = "".join(temp_text_list)

                if global_match_count >= 50:
                    break

            # 不再需要排序 entry_placeholders
            placeholder_order[key] = entry_placeholders
            new_dict[key] = current_text

        return new_dict, placeholder_order

    # <--- 修改签名，接收编译好的模式 -->
    def _process_affixes(self, text_dict: Dict[str, str], compiled_patterns_with_source: List[Tuple[str, re.Pattern]]) -> Tuple[Dict[str, str], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
        """处理前后缀提取 (使用预编译正则)"""
        prefix_codes: Dict[str, List[Dict]] = {}
        suffix_codes: Dict[str, List[Dict]] = {}
        processed_text_dict = {}

        for key, text in text_dict.items():
            if not isinstance(text, str):
                processed_text_dict[key] = text
                prefix_codes[key] = []
                suffix_codes[key] = []
                continue

            current_text = text
            current_prefixes: List[Dict] = []
            current_suffixes: List[Dict] = []

            # 前缀提取 - 使用预编译模式
            for pattern_str, pattern in compiled_patterns_with_source: # <--- 使用元组解包
                while True:
                    try:
                        match = pattern.match(current_text)
                        if match:
                            prefix_text = match.group(0)
                            if len(prefix_text) == len(current_text):
                                break
                            current_prefixes.append({"prefix": prefix_text, "pattern": pattern_str}) # 使用 pattern_str
                            current_text = current_text[len(prefix_text):]
                        else:
                            break
                    except Exception as e:
                        self.error(f"处理前缀时出错 (key: {key}, pattern: {pattern.pattern})", e)
                        break

            # 后缀提取 - 使用预编译模式
            for pattern_str, pattern in compiled_patterns_with_source: # <--- 使用元组解包
                made_change = True
                while made_change:
                    made_change = False
                    best_match = None
                    try:
                        possible_matches = list(pattern.finditer(current_text))
                        for match in reversed(possible_matches):
                            if match.end() == len(current_text):
                                if match.start() == 0:
                                    continue
                                best_match = match
                                break

                        if best_match:
                            suffix_text = best_match.group(0)
                            current_suffixes.insert(0, {"suffix": suffix_text, "pattern": pattern_str}) # 使用 pattern_str
                            current_text = current_text[:best_match.start()]
                            made_change = True
                    except Exception as e:
                         self.error(f"处理后缀时出错 (key: {key}, pattern: {pattern.pattern})", e)
                         made_change = False

            # 空文本检查(逻辑不变)
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

    def _restore_affixes(self, text_dict: Dict[str, str], prefix_codes: Dict[str, List[Dict]], suffix_codes: Dict[str, List[Dict]]) -> Dict[str, str]:
        """还原前后缀 """
        restored_dict = {}
        for key, text in text_dict.items():
            if not isinstance(text, str):
                restored_dict[key] = text
                continue

            prefix_str = ''.join([item.get('prefix','') for item in prefix_codes.get(key, [])])
            suffix_str = ''.join([item.get('suffix','') for item in suffix_codes.get(key, [])])
            restored = f"{prefix_str}{text}{suffix_str}"
            restored_dict[key] = restored
        return restored_dict

    def _restore_special_placeholders(self, text_dict: Dict[str, str], placeholder_order: Dict[str, List[Dict[str, str]]]) -> Dict[str, str]:
        """占位符还原 (保持不变，依赖 reversed 和 replace count=1)"""
        new_dic = {}
        for key, text in text_dict.items():
            if not isinstance(text, str):
                new_dic[key] = text
                continue

            placeholders_for_key = placeholder_order.get(key, [])

            if not placeholders_for_key:
                new_dic[key] = text
            else:
                restored_text = text
                for item in reversed(placeholders_for_key):
                    placeholder_text = item.get("placeholder")
                    original_text = item.get("original")
                    if placeholder_text is not None and original_text is not None:
                         if placeholder_text in restored_text:
                             restored_text = restored_text.replace(placeholder_text, original_text, 1)
                         # else: # 移除警告，减少干扰
                         #     pass
                new_dic[key] = restored_text
        return new_dic

    # 修改译前替换，使用预编译规则
    def replace_before_translation(self, config, text_dict: dict) -> dict:
        processed_text_dict = text_dict.copy()
        compiled_rules = getattr(self, "compiled_pre_rules", []) # 使用实例属性
        if not compiled_rules:
            return processed_text_dict

        for k in processed_text_dict:
            if not isinstance(processed_text_dict[k], str):
                continue

            original_text = processed_text_dict[k]
            current_text = original_text

            for rule in compiled_rules:
                compiled_pattern = rule.get("compiled")
                src_text = rule.get("src")
                dst_text = rule.get("dst", "")

                try:
                    if compiled_pattern:
                        new_text = compiled_pattern.sub(dst_text, current_text)
                        if new_text != current_text:
                            current_text = new_text
                        continue
                    elif src_text and isinstance(src_text, str) and src_text in current_text:
                        replace_with = dst_text if isinstance(dst_text, str) else ""
                        current_text = current_text.replace(src_text, replace_with)
                except Exception as e:
                    # 使用 Base.error 记录日志，如果可用
                    if hasattr(self, 'error'):
                        self.error(f"译前替换时出错 (key: {k}, rule: {rule})", e)
                    else:
                        print(f"[Error][TextProcessor]: 译前替换时出错 (key: {k}, rule: {rule}): {e}")
                    continue

            if current_text != original_text:
                 processed_text_dict[k] = current_text

        return processed_text_dict

    # 修改译后替换，使用预编译规则 (逻辑同上)
    def replace_after_translation(self, config, text_dict: dict) -> dict:
        processed_text_dict = text_dict.copy()
        compiled_rules = getattr(self, "compiled_post_rules", []) # 使用实例属性
        if not compiled_rules:
             return processed_text_dict

        for k in processed_text_dict:
            if not isinstance(processed_text_dict[k], str):
                continue

            original_text = processed_text_dict[k]
            current_text = original_text

            for rule in compiled_rules:
                compiled_pattern = rule.get("compiled")
                src_text = rule.get("src")
                dst_text = rule.get("dst", "")

                try:
                    if compiled_pattern:
                        new_text = compiled_pattern.sub(dst_text, current_text)
                        if new_text != current_text:
                            current_text = new_text
                        continue
                    elif src_text and isinstance(src_text, str) and src_text in current_text:
                        replace_with = dst_text if isinstance(dst_text, str) else ""
                        current_text = current_text.replace(src_text, replace_with)
                except Exception as e:
                    if hasattr(self, 'error'):
                        self.error(f"译后替换时出错 (key: {k}, rule: {rule})", e)
                    else:
                        print(f"[Error][TextProcessor]: 译后替换时出错 (key: {k}, rule: {rule}): {e}")
                    continue

            if current_text != original_text:
                 processed_text_dict[k] = current_text

        return processed_text_dict


    # 数字序号预处理
    def digital_sequence_preprocessing(self, text_dict: dict) -> dict:
        processed_dict = {}
        for k, v in text_dict.items():
            if not isinstance(v, str):
                processed_dict[k] = v
                continue
            processed_dict[k] = self.PRE_DIGIT_PATTERN.sub(r'【\1】', v, count=1)
        return processed_dict

    #  数字序号恢复
    def digital_sequence_recovery(self, text_dict: dict) -> dict:
        processed_dict = {}
        for k, v in text_dict.items():
            if not isinstance(v, str):
                 processed_dict[k] = v
                 continue
            processed_dict[k] = self.POST_DIGIT_PATTERN.sub(r'\1.', v, count=1)
        return processed_dict

    # 预提取前后缀的空格与换行
    def strip_and_record_affix_whitespace(self, text_dict):
        processed_text_dict = {}
        processing_info = {}

        for key, original_text in text_dict.items():
            if not isinstance(original_text, str):
                processed_text_dict[key] = original_text
                processing_info[key] = {'prefix': '', 'suffix': ''}
                continue

            match = self.AFFIX_PATTERN.match(original_text)
            if match:
                prefix = match.group(1)
                core_text = match.group(2)
                suffix = match.group(3)
                processed_text_dict[key] = core_text
                processing_info[key] = {'prefix': prefix, 'suffix': suffix}
            else:
                processed_text_dict[key] = original_text
                processing_info[key] = {'prefix': '', 'suffix': ''}

        return processed_text_dict, processing_info

    # 还原前后缀的空格与换行
    def restore_affix_whitespace(self, processing_info, processed_dict):
        restored_text_dict = {}
        for key, core_text in processed_dict.items():
            safe_core_text = core_text if isinstance(core_text, str) else ""

            if key in processing_info:
                info = processing_info[key]
                prefix = info.get('prefix', '')
                suffix = info.get('suffix', '')
                prefix_str = prefix if isinstance(prefix, str) else ''
                suffix_str = suffix if isinstance(suffix, str) else ''
                restored_text_dict[key] = prefix_str + safe_core_text + suffix_str
            else:
                restored_text_dict[key] = safe_core_text
        return restored_text_dict