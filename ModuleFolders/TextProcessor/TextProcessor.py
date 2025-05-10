import json
import os
import re
from typing import List, Dict, Tuple, Any, Optional 

from Base.Base import Base 

class TextProcessor(Base):
    # 定义日语字符集的正则表达式
    JAPANESE_CHAR_SET_CONTENT = (
        r'\u3040-\u309F'  
        r'\u30A0-\u30FF'  
        r'\u30FB-\u30FE'  
        r'\uFF65-\uFF9F'  
        r'\u4E00-\u9FFF'  
        r'\u3400-\u4DBF'  
        r'\u3001-\u303F'  
        r'\uff01-\uff5e'  
    )

    # 正则库路径
    DEFAULT_REGEX_DIR = os.path.join(".", "Resource", "Regex", "regex.json")

    # 数字序号与空白内容正则
    RE_DIGITAL_SEQ_PRE_STR = r'^(\d+)\.'
    RE_DIGITAL_SEQ_REC_STR = r'^【(\d+)】'
    RE_WHITESPACE_AFFIX_STR = r'^(\s*)(.*?)(\s*)$'

    def __init__(self, config: Any): 
        super().__init__()

        current_regex_dir = self.DEFAULT_REGEX_DIR

        # 预编译固定处理的正则表达式
        self.RE_DIGITAL_SEQ_PRE = re.compile(self.RE_DIGITAL_SEQ_PRE_STR)
        self.RE_DIGITAL_SEQ_REC = re.compile(self.RE_DIGITAL_SEQ_REC_STR)
        self.RE_WHITESPACE_AFFIX = re.compile(self.RE_WHITESPACE_AFFIX_STR, re.DOTALL)
        
        ja_affix_pattern_str = (
            rf'(^[^{self.JAPANESE_CHAR_SET_CONTENT}]*)'  # Group 1: Prefix
            rf'(.*?)'                                   # Group 2: Core text
            rf'([^{self.JAPANESE_CHAR_SET_CONTENT}]*$)' # Group 3: Suffix
        )


        # 预编译日语字符集的正则
        self.RE_JA_AFFIX = re.compile(ja_affix_pattern_str, re.DOTALL)


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


    def _compile_translation_rules(self, rules_data: Optional[List[Dict]]) -> List[Dict]:
        compiled_rules = []
        if not rules_data:
            return compiled_rules
            
        # 遍历文本替换的数据    
        for rule in rules_data:
            new_rule = rule.copy()

            # 如果有正则，则进行预编译，如果没有则原样
            if regex_str := rule.get("regex"):
                new_rule["compiled_regex"] = re.compile(regex_str)

            compiled_rules.append(new_rule)
        return compiled_rules

    def _prepare_code_pattern_strings(self, exclusion_list_data: Optional[List[Dict]], regex_dir_path: str) -> List[str]:
        patterns: List[str] = []

        # 读取正则库内容
        with open(regex_dir_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            file_patterns = [item["regex"] for item in data if isinstance(item, dict) and "regex" in item and item["regex"]]
        patterns.extend(file_patterns)

        # 读取禁翻表内容
        if exclusion_list_data:
            for item in exclusion_list_data:
                if regex_str := item.get("regex"):
                    if regex_str: patterns.append(regex_str)
                elif markers := item.get("markers"):
                    if markers: patterns.append(re.escape(markers))
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
    def replace_all(self, config, source_lang: str, text_dict: Dict[str, str]) -> Tuple[Dict[str, str], Dict, Dict, Dict, Dict]:

        # 存储处理后信息的变量
        processed_text = {k: v for k, v in text_dict.items()}
        prefix_codes: Dict[str, List[Dict]] = {}
        suffix_codes: Dict[str, List[Dict]] = {}
        placeholder_order: Dict[str, List[Dict[str, str]]] = {}
        affix_whitespace_storage: Dict[str, Dict[str,str]] = {}

        # 获取各个配置信息,减少再次传递
        pre_translation_switch = config.pre_translation_switch
        auto_process_text_code_segment = config.auto_process_text_code_segment
        target_platform = config.target_platform

        # 译前替换
        if pre_translation_switch:
            processed_text = self.replace_before_translation(processed_text) 

        # 空白换行，非日语文本前后缀处理
        processed_text, affix_whitespace_storage = self.strip_and_record_affixes(processed_text, source_lang) 

        # 自动预处理
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

        #处理数字序号    
        processed_text = self.digital_sequence_preprocessing(processed_text) 

        return processed_text, prefix_codes, suffix_codes, placeholder_order, affix_whitespace_storage

    # 译后文本处理
    def restore_all(self, config, text_dict: Dict[str, str], prefix_codes: Dict, suffix_codes: Dict, placeholder_order: Dict, affix_whitespace_storage: Dict) -> Dict[str, str]:
        restored = text_dict.copy()

        # 获取各个配置信息
        auto_process_text_code_segment = config.auto_process_text_code_segment
        post_translation_switch = config.post_translation_switch 

        # 自动处理还原
        if auto_process_text_code_segment:
            restored = self._restore_special_placeholders(restored, placeholder_order)
            restored = self._restore_affixes(restored, prefix_codes, suffix_codes)

        # 译后替换
        if post_translation_switch:
            restored = self.replace_after_translation(restored) 

        # 数字序号还原
        restored = self.digital_sequence_recovery(restored) 

        # 前后空白换行，非日语文本还原
        restored = self.restore_affix_whitespace(affix_whitespace_storage, restored) 

        return restored

    # 处理并占位文本中间内容
    def _replace_special_placeholders(self, target_platform: str, text_dict: Dict[str, str], compiled_placeholder_patterns: List[re.Pattern]) -> Tuple[Dict[str, str], Dict[str, List[Dict[str, str]]]]:
        new_dict = {}
        placeholder_order: Dict[str, List[Dict[str, str]]] = {}
        global_match_count = 0

        for key, original_text in text_dict.items():
            current_text = original_text
            entry_placeholders: List[Dict[str, str]] = []
            sakura_match_count = 0

            current_pattern_str_for_replacer = "" # Will be set in the loop

            def create_replacer(pattern_obj_for_replacer: re.Pattern):
                nonlocal global_match_count, sakura_match_count, entry_placeholders 
                
                current_pattern_str_for_replacer = pattern_obj_for_replacer.pattern

                def replacer_inner(match):
                    nonlocal global_match_count, sakura_match_count 
                    if global_match_count >= 50:
                        return match.group(0)

                    global_match_count += 1
                    sakura_match_count += 1
                    original_match_val = match.group(0)
                    
                    placeholder_val = f"[P{global_match_count}]"
                    if target_platform == "sakura":
                        placeholder_val = "↓" * sakura_match_count
                    
                    entry_placeholders.append({
                        "placeholder": placeholder_val,
                        "original": original_match_val,
                        "pattern": current_pattern_str_for_replacer
                    })
                    return placeholder_val
                return replacer_inner

            for pattern_obj in compiled_placeholder_patterns:

                single_pattern_replacements: List[Dict[str, str]] = []
                
                def replacer_for_this_pattern(match_obj):
                    nonlocal global_match_count, sakura_match_count, single_pattern_replacements
                    
                    if global_match_count >= 50:
                        return match_obj.group(0)
                    
                    global_match_count += 1
                    sakura_match_count += 1
                    original_match_val = match_obj.group(0)

                    placeholder_val = f"[P{global_match_count}]"
                    if target_platform == "sakura":
                        placeholder_val = "↓" * sakura_match_count
                    
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
    def _restore_special_placeholders(self, text_dict: Dict[str, str], placeholder_order: Dict[str, List[Dict[str, str]]]) -> Dict[str, str]:
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
    def _process_affixes(self, text_dict: Dict[str, str], compiled_prefix_patterns: List[re.Pattern], compiled_suffix_patterns: List[re.Pattern]) -> Tuple[Dict[str, str], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
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
                        if match:
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
                        if best_match:
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
    def _restore_affixes(self, text_dict: Dict[str, str], prefix_codes: Dict[str, List[Dict]], suffix_codes: Dict[str, List[Dict]]) -> Dict[str, str]:
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
                    current_text = compiled_regex_obj.sub(dst_text, current_text)
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
                    current_text = compiled_regex_obj.sub(dst_text, current_text)
                    continue

                elif src_text and src_text in current_text:
                    current_text = current_text.replace(src_text, dst_text)

            if current_text != original_text_val:
                 processed_text_dict[k] = current_text

        return processed_text_dict

    # 处理数字序列
    def digital_sequence_preprocessing(self, text_dict: dict) -> dict:
        for k in text_dict: 
            # 将例如 "1." 替换为 "【1】"，只替换文本开头的第一个匹配项
            text_dict[k] = self.RE_DIGITAL_SEQ_PRE.sub(r'【\1】', text_dict[k], count=1)
        return text_dict

    # 还原数字序列
    def digital_sequence_recovery(self, text_dict: dict) -> dict:
        for k in text_dict: 
            text_dict[k] = self.RE_DIGITAL_SEQ_REC.sub(r'\1.', text_dict[k], count=1)
        return text_dict

    # 处理前后缀的空格与换行，以及非日语文本
    def strip_and_record_affixes(self, text_dict: Dict[str,str], source_lang: str) -> Tuple[Dict[str,str], Dict[str,Dict[str,str]]]:
        processed_text_dict: Dict[str,str] = {}
        processing_info: Dict[str,Dict[str,str]] = {}
        
        # 根据源语言选择正则表达式
        pattern_to_use = self.RE_WHITESPACE_AFFIX
        if source_lang == 'ja' or source_lang == 'japanese':
            pattern_to_use = self.RE_JA_AFFIX
            
        for key, original_text in text_dict.items():

            # 检查是否是字符串
            if not isinstance(original_text, str):
                processed_text_dict[key] = original_text 
                processing_info[key] = {'prefix': '', 'suffix': ''} 
                continue

            match = pattern_to_use.match(original_text)
            if match:
                prefix, core_text, suffix = match.group(1), match.group(2), match.group(3)
                if prefix == "[": core_text, prefix = "[" + core_text, "" # 特殊处理，前缀是左方括号
                if suffix == "]": core_text, suffix = core_text + "]", "" # 特殊处理，后缀是右方括号
                if suffix.isdigit(): core_text, suffix = core_text + suffix, "" # 特殊处理，后缀是数字
                if not core_text.strip(): core_text, prefix, suffix = original_text, '', '' # 特殊处理，提取后，中间内容为空
                    
                processed_text_dict[key] = core_text
                processing_info[key] = {'prefix': prefix, 'suffix': suffix}
            else: 
                processed_text_dict[key] = original_text
                processing_info[key] = {'prefix': '', 'suffix': ''}
        return processed_text_dict, processing_info

    # 还原前后缀的空格与换行
    def restore_affix_whitespace(self, processing_info: Dict[str,Dict[str,str]], processed_dict: Dict[str,str]) -> Dict[str,str]:
        restored_text_dict: Dict[str,str] = {}
        for key, core_text in processed_dict.items():
            info = processing_info.get(key)
            if info:
                restored_text_dict[key] = info.get('prefix', '') + core_text + info.get('suffix', '')
            else:
                restored_text_dict[key] = core_text 
        return restored_text_dict