import re
from typing import List, Dict, Tuple, Pattern # 增加 Pattern 类型导入
import functools # 导入 functools 用于 lru_cache

from Base.Base import Base


class TextProcessor(Base):
    # --- 预编译的类级别正则表达式 ---
    PRE_DIGIT_PATTERN = re.compile(r'^(\d+)\.')
    POST_DIGIT_PATTERN = re.compile(r'^【(\d+)】')
    AFFIX_PATTERN = re.compile(r'^(\s*)(.*?)(\s*)$', re.DOTALL)
    # --- 预编译 End ---

    # 修改构造函数，接收正则列表并预编译
    def __init__(self, code_pattern_list: List[str], config = None): # 添加 config 参数
        super().__init__() # 调用父类的构造函数
        # --- 正则预编译 ---
        self.compiled_code_patterns: List[Pattern] = self._compile_patterns(code_pattern_list)
        # --- 正则预编译 End ---

        # --- 预编译译前/译后规则 ---
        # 从传入的 config 对象获取规则数据，如果 config 为 None 则使用空列表
        pre_data = config.pre_translation_data if config and hasattr(config, 'pre_translation_data') else []
        post_data = config.post_translation_data if config and hasattr(config, 'post_translation_data') else []
        self.compiled_pre_rules = self._compile_translation_rules(pre_data)
        self.compiled_post_rules = self._compile_translation_rules(post_data)
        # --- 预编译 End ---

        # print(f"[DEBUG] TextProcessor initialized with {len(self.compiled_code_patterns)} code patterns, "
        #       f"{len(self.compiled_pre_rules)} pre-rules, {len(self.compiled_post_rules)} post-rules.") # 调试信息

    @staticmethod
    @functools.lru_cache(maxsize=None) # 使用 lru_cache 缓存编译结果，避免重复编译相同模式
    def _compile_pattern_cached(pattern_str: str) -> Pattern | None:
        """编译单个正则表达式模式，处理可能的错误，并缓存结果"""
        try:
            # 忽略空模式
            if not pattern_str:
                return None
            # 尝试编译，使用 IGNORECASE 和 MULTILINE
            return re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
        except re.error as e:
            # 如果编译失败，打印警告并返回 None
            # 使用 Base 的 error 方法记录日志，如果可用
            if hasattr(TextProcessor, 'error'):
                 TextProcessor().error(f"正则编译错误！！ pattern '{pattern_str}'", e)
            else:
                 print(f"[Warning][TextProcessor]: 正则编译错误！！ pattern '{pattern_str}': {e}")
            return None

    def _compile_patterns(self, pattern_list: List[str]) -> List[Pattern]:
        """编译正则表达式列表，过滤掉无效或空的模式"""
        compiled = []
        for p_str in pattern_list:
            compiled_pattern = self._compile_pattern_cached(p_str)
            if compiled_pattern: # 只添加成功编译的模式
                compiled.append(compiled_pattern)
        return compiled

    def _compile_translation_rules(self, rules_data):
        """编译译前/译后替换规则中的正则表达式"""
        compiled_rules = []
        if not rules_data:
            return compiled_rules
        for rule in rules_data:
            # 确保 rule 是字典类型
            if not isinstance(rule, dict):
                continue
            regex_pattern = rule.get("regex")
            compiled_pattern = None
            if regex_pattern:
                compiled_pattern = self._compile_pattern_cached(regex_pattern) # 复用缓存编译
            compiled_rules.append({
                "compiled": compiled_pattern, # 存储编译好的模式或 None
                "src": rule.get("src"),
                "dst": rule.get("dst", "")
            })
        return compiled_rules

    # 译前文本处理
    def replace_all(self, config, text_dict: Dict[str, str]) -> Tuple[Dict[str, str], Dict, Dict, Dict, Dict]:
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
            processed_text, prefix_codes, suffix_codes = self._process_affixes(processed_text)

            # 特殊文本占位替换 (使用预编译正则)
            processed_text, placeholder_order = self._replace_special_placeholders(
                config.target_platform, # 假设 config 对象可访问 target_platform
                processed_text
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

    def _replace_special_placeholders(self, target_platform: str, text_dict: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, List[Dict[str, str]]]]:
        """特殊文本占位替换 (使用预编译正则)"""
        new_dict = {}
        placeholder_order: Dict[str, List[Dict[str, str]]] = {}
        global_match_count = 0

        for key, original_text in text_dict.items():
            current_text = original_text
            entry_placeholders: List[Dict[str, str]] = []
            sakura_match_count = 0

            replacement_info_holder = []

            def replacer(match, pattern_str_ref): # 修改：传递 pattern 字符串引用
                nonlocal global_match_count, sakura_match_count

                if global_match_count >= 50:
                    return match.group(0)

                global_match_count += 1
                sakura_match_count += 1

                original_match = match.group(0)
                if target_platform == "sakura":
                    placeholder = "↓" * sakura_match_count
                else:
                    placeholder = f"[P{global_match_count}]"

                replacement_info_holder.append({
                    "placeholder": placeholder,
                    "original": original_match,
                    "pattern": pattern_str_ref # 使用传入的 pattern 字符串
                })

                return placeholder

            # 遍历预编译的模式对象
            for pattern in self.compiled_code_patterns: # 使用 self.compiled_code_patterns
                replacement_info_holder.clear()
                # 使用 functools.partial 传递 pattern.pattern (原始字符串) 给 replacer
                current_text = pattern.sub(functools.partial(replacer, pattern_str_ref=pattern.pattern), current_text)
                entry_placeholders.extend(replacement_info_holder)

                if global_match_count >= 50:
                    break

            placeholder_order[key] = entry_placeholders
            new_dict[key] = current_text

        return new_dict, placeholder_order

    def _process_affixes(self, text_dict: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
        """处理前后缀提取 (使用预编译正则)"""
        prefix_codes: Dict[str, List[Dict]] = {}
        suffix_codes: Dict[str, List[Dict]] = {}
        processed_text_dict = {}

        for key, text in text_dict.items():
            current_text = text
            current_prefixes: List[Dict] = []
            current_suffixes: List[Dict] = []

            # 前缀提取 - 使用预编译模式
            for pattern in self.compiled_code_patterns: # 使用预编译列表
                while True:
                    match = pattern.match(current_text)
                    if match:
                        prefix_text = match.group(0)
                        current_prefixes.append({"prefix": prefix_text, "pattern": pattern.pattern}) # 存储原始 pattern 字符串
                        current_text = current_text[len(prefix_text):]
                    else:
                        break

            # 后缀提取 - 使用预编译模式
            for pattern in self.compiled_code_patterns: # 使用预编译列表
                made_change = True
                while made_change:
                    made_change = False
                    best_match = None
                    for match in pattern.finditer(current_text):
                        if match.end() == len(current_text):
                            best_match = match

                    if best_match:
                        suffix_text = best_match.group(0)
                        current_suffixes.insert(0, {"suffix": suffix_text, "pattern": pattern.pattern}) # 存储原始 pattern 字符串
                        current_text = current_text[:best_match.start()]
                        made_change = True

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
            prefix_str = ''.join([item['prefix'] for item in prefix_codes.get(key, [])])
            suffix_str = ''.join([item['suffix'] for item in suffix_codes.get(key, [])])
            restored = f"{prefix_str}{text}{suffix_str}"
            restored_dict[key] = restored
        return restored_dict

    def _restore_special_placeholders(self, text_dict: Dict[str, str], placeholder_order: Dict[str, List[Dict[str, str]]]) -> Dict[str, str]:
        """占位符还原"""
        new_dic = {}
        for key, text in text_dict.items():
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
                         else:
                             # 使用 Base 的 warning 方法记录日志，如果可用
                             if hasattr(self, 'warning'):
                                 self.warning(f"占位符 '{placeholder_text}' 在 key '{key}' 的文本中未找到，无法还原。原文: '{original_text}'")
                             else:
                                 print(f"[Warning]: Placeholder '{placeholder_text}' not found in text for key '{key}' during restoration. Original: '{original_text}'")
                new_dic[key] = restored_text
        return new_dic

    # 修改译前替换，使用预编译规则
    def replace_before_translation(self, config, text_dict: dict) -> dict:
        processed_text_dict = text_dict.copy()
        # 获取预编译规则 (使用 getattr 安全获取，如果未初始化则重新编译)
        compiled_rules = getattr(self, "compiled_pre_rules", self._compile_translation_rules(config.pre_translation_data))

        for k in processed_text_dict:
            original_text = processed_text_dict[k]
            current_text = original_text

            for rule in compiled_rules:
                compiled_pattern = rule["compiled"]
                src_text = rule["src"]
                dst_text = rule["dst"]

                if compiled_pattern: # 优先使用预编译的正则
                    new_text = compiled_pattern.sub(dst_text, current_text)
                    if new_text != current_text:
                        current_text = new_text
                    continue # 正则匹配后跳过普通替换

                elif src_text and src_text in current_text: # 正则不存在或无效，执行普通替换
                    current_text = current_text.replace(src_text, dst_text)

            if current_text != original_text:
                 processed_text_dict[k] = current_text

        return processed_text_dict

    # 修改译后替换，使用预编译规则 (逻辑同上)
    def replace_after_translation(self, config, text_dict: dict) -> dict:
        processed_text_dict = text_dict.copy()
        # 获取预编译规则
        compiled_rules = getattr(self, "compiled_post_rules", self._compile_translation_rules(config.post_translation_data))

        for k in processed_text_dict:
            original_text = processed_text_dict[k]
            current_text = original_text

            for rule in compiled_rules:
                compiled_pattern = rule["compiled"]
                src_text = rule["src"]
                dst_text = rule["dst"]

                if compiled_pattern:
                    new_text = compiled_pattern.sub(dst_text, current_text)
                    if new_text != current_text:
                        current_text = new_text
                    continue
                elif src_text and src_text in current_text:
                     current_text = current_text.replace(src_text, dst_text)

            if current_text != original_text:
                 processed_text_dict[k] = current_text

        return processed_text_dict

    # 数字序号预处理
    def digital_sequence_preprocessing(self, text_dict: dict) -> dict:
        processed_dict = {}
        for k, v in text_dict.items():
             # 使用预编译的类级别模式
            processed_dict[k] = self.PRE_DIGIT_PATTERN.sub(r'【\1】', v, count=1)
        return processed_dict

    #  数字序号恢复
    def digital_sequence_recovery(self, text_dict: dict) -> dict:
        processed_dict = {}
        for k, v in text_dict.items():
             # 使用预编译的类级别模式
            processed_dict[k] = self.POST_DIGIT_PATTERN.sub(r'\1.', v, count=1)
        return processed_dict

    # 预提取前后缀的空格与换行
    def strip_and_record_affix_whitespace(self, text_dict):
        processed_text_dict = {}
        processing_info = {}

        for key, original_text in text_dict.items():
            if not isinstance(original_text, str):
                processed_text_dict[key] = original_text
                continue

            match = self.AFFIX_PATTERN.match(original_text) # 使用类属性
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

    # 还原前后缀的空格与换行 (无需修改)
    def restore_affix_whitespace(self, processing_info, processed_dict):
        restored_text_dict = {}
        for key, core_text in processed_dict.items():
            if key in processing_info:
                info = processing_info[key]
                prefix = info.get('prefix', '')
                suffix = info.get('suffix', '')
                restored_text_dict[key] = prefix + core_text + suffix
            else:
                restored_text_dict[key] = core_text
        return restored_text_dict