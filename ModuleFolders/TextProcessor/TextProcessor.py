import re
from typing import List, Dict, Tuple

from Base.Base import Base


class TextProcessor(Base):
    def __init__(self):
        pass

    # 译前文本处理
    def replace_all(self, config, text_dict: Dict[str, str], code_pattern_list: List[str]):
        """执行全部替换操作"""
        processed_text = {k: v for k, v in text_dict.items()}
        prefix_codes, suffix_codes, placeholder_order = {}, {}, {}

        # 译前替换
        if config.pre_translation_switch:
            processed_text = TextProcessor.replace_before_translation(self,config, processed_text) 

        # 预处理文本前后的空格与换行
        processed_text, affix_whitespace_storage = TextProcessor.strip_and_record_affix_whitespace(self,processed_text) 

        # 自动处理代码段
        if config.auto_process_text_code_segment:
            # 处理前后缀 
            processed_text, prefix_codes, suffix_codes = TextProcessor._process_affixes(self,processed_text, code_pattern_list)

            # 特殊文本占位替换 
            processed_text, placeholder_order = TextProcessor._replace_special_placeholders(self,
                config.target_platform,
                processed_text,
                code_pattern_list
            )

        # 数字序号预处理
        processed_text = TextProcessor.digital_sequence_preprocessing(self,processed_text) 

        return processed_text, prefix_codes, suffix_codes, placeholder_order, affix_whitespace_storage

    # 译后文本处理
    def restore_all(self, config, text_dict: Dict[str, str], prefix_codes: Dict, suffix_codes: Dict, placeholder_order: Dict, affix_whitespace_storage: Dict) -> Dict[str, str]:
        """执行全部还原操作"""
        restored = text_dict.copy()

        # 自动处理代码段
        if config.auto_process_text_code_segment:
            # 占位符恢复
            restored = TextProcessor._restore_special_placeholders(self,restored, placeholder_order)
            # 前后缀恢复
            restored = TextProcessor._restore_affixes(self,restored, prefix_codes, suffix_codes)

        # 译后替换
        if config.post_translation_switch:
            restored = TextProcessor.replace_after_translation(self,config, restored) 

        # 数字序号恢复
        restored = TextProcessor.digital_sequence_recovery(self,restored) 

        # 前后缀的换行空格恢复
        restored = TextProcessor.restore_affix_whitespace(self, affix_whitespace_storage, restored) 

        return restored

    def _replace_special_placeholders(self, target_platform: str, text_dict: Dict[str, str], code_pattern_list: List[str]) -> Tuple[Dict[str, str], Dict[str, List[Dict[str, str]]]]:
        """特殊文本占位替换"""

        placeholder_patterns = TextProcessor._build_special_placeholder_pattern(self,code_pattern_list)
        new_dict = {}
        placeholder_order: Dict[str, List[Dict[str, str]]] = {}
        global_match_count = 0  # 全局匹配计数器，跨所有文本共享

        for key, original_text in text_dict.items():
            current_text = original_text
            entry_placeholders: List[Dict[str, str]] = []
            sakura_match_count = 0  # Sakura计数器，每个文本条目独立

            # 存储本次替换操作的信息，以便能在 re.sub 的 repl 函数外部访问
            # 使用列表作为可变容器
            replacement_info_holder = []

            def replacer(match):
                nonlocal global_match_count, sakura_match_count # 允许修改外部函数的变量

                # 检查全局计数器限制
                # 注意：即使超出限制，re.sub 仍会完成当前模式的所有查找，
                # 但我们只对达到限制前的匹配进行替换和记录。
                # 一个更严格的实现可能需要finditer并手动构建字符串，但会更复杂。
                # 当前实现：达到限制后，不再生成新占位符，并可能返回原匹配文本。
                if global_match_count >= 50:
                    # 达到上限，不再替换，返回原始内容
                    return match.group(0)

                global_match_count += 1
                sakura_match_count += 1

                original_match = match.group(0)
                if target_platform == "sakura":
                    placeholder = "↓" * sakura_match_count
                else:
                    placeholder = f"[P{global_match_count}]" # 使用全局计数

                # 暂存替换信息
                replacement_info_holder.append({
                    "placeholder": placeholder,
                    "original": original_match,
                    "pattern": pattern_str # pattern_str 需要在外部循环中可用
                })

                return placeholder # 返回替换用的占位符

            # 遍历每个正则模式
            for pattern_str in placeholder_patterns:
                # 清空上次模式的暂存信息
                replacement_info_holder.clear()

                try:
                    # 编译正则表达式
                    pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                    # 使用 re.sub 和回调函数替换所有匹配项
                    current_text = pattern.sub(replacer, current_text)

                    # 将本次模式成功替换的信息添加到总列表
                    # 按原样添加即可，恢复时反转
                    entry_placeholders.extend(replacement_info_holder)

                except re.error as e:
                    print(f"[Warning]: 占位正则匹配出现问题！！ pattern '{pattern_str}' on key '{key}': {e}")
                    # 可以选择跳过这个模式或采取其他错误处理
                    continue
                
                # 如果全局计数达到上限，可以提前结束此文本条目的模式遍历
                if global_match_count >= 50:
                    #print(f"Warning: Global placeholder limit (50) reached while processing key '{key}'. Stopping further replacements for this entry and subsequent entries.")
                    # 注意：这里仅停止当前条目的进一步模式匹配，
                    # global_match_count 已达上限，下一个条目开始时也会立即检查。
                    break


            placeholder_order[key] = entry_placeholders # 存储这个key的所有替换记录
            new_dict[key] = current_text # 存储处理后的文本


        return new_dict, placeholder_order

    def _build_special_placeholder_pattern(self, code_pattern_list: List[str]) -> List[str]:
        r"""构建特殊占位符匹配的正则表达式 列表
        每个模式前后添加 \s* 以匹配可能的空白。
        对于 \\\\. 模式，增强后的正则变为 \s*\\\\.\s*，这会匹配反斜杠前后可能的空白（包括换行符 \n）。
        如果文本中的反斜杠附近存在换行符（例如 ...\.\n...），增强后的正则会连带匹配到 \n。
        """
        enhanced_patterns = []
        for p in code_pattern_list:
            if p:
                # 使用原始字符串避免过多反斜杠转义问题
                enhanced = fr"\s*{p}\s*"
                enhanced_patterns.append(enhanced)

        return enhanced_patterns

    def _build_affixes_patterns(self, code_pattern_list: List[str]) -> Tuple[List[str], List[str]]:
        """构建前后缀正则表达式 列表 """
        if not code_pattern_list:
            return [], []
        enhanced_patterns = []
        for p in code_pattern_list:
            if p:
                enhanced = fr"\s*{p}\s*"
                enhanced_patterns.append(enhanced)

        # 前后缀使用相同的模式列表
        return enhanced_patterns, enhanced_patterns

    def _restore_special_placeholders(self, text_dict: Dict[str, str], placeholder_order: Dict[str, List[Dict[str, str]]]) -> Dict[str, str]:
        """占位符还原"""
        new_dic = {}
        for key, text in text_dict.items():
            placeholders_for_key = placeholder_order.get(key, [])

            if not placeholders_for_key:
                new_dic[key] = text
            else:
                # 必须反向还原，因为后面的替换可能包含了前面替换的占位符，
                # 或者对于 Sakura 的 "↓" * n 格式，长度是递增的。
                # 反向保证先还原最内层/最后进行的替换。
                restored_text = text
                for item in reversed(placeholders_for_key):
                    placeholder_text = item.get("placeholder")
                    original_text = item.get("original")
                    # 使用 count=1 确保每次只替换一个，防止一个占位符意外匹配多次
                    # (虽然 P{n} 应该是唯一的，但 Sakura 的 ↓... 可能不是)
                    if placeholder_text is not None and original_text is not None:
                         # 增加保护：确保占位符真的在文本中，防止无限循环或错误
                         # （理论上应该在，但以防万一）
                         if placeholder_text in restored_text:
                             restored_text = restored_text.replace(placeholder_text, original_text, 1)
                         else:
                             # 如果占位符意外丢失（例如被翻译引擎修改），记录一个警告
                             print(f"[Warning]: Placeholder '{placeholder_text}' not found in text for key '{key}' during restoration. Original: '{original_text}'")


                new_dic[key] = restored_text

        return new_dic

    def _process_affixes(self, text_dict: Dict[str, str], code_pattern_list: List[str]) -> Tuple[Dict[str, str], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
        """处理前后缀提取"""
        prefix_codes: Dict[str, List[Dict]] = {}
        suffix_codes: Dict[str, List[Dict]] = {}
        processed_text_dict = {} # 创建新字典以避免修改迭代中的字典

        prefix_patterns, suffix_patterns = TextProcessor._build_affixes_patterns(self,code_pattern_list)

        for key, text in text_dict.items():
            current_text = text # 操作副本
            current_prefixes: List[Dict] = []
            current_suffixes: List[Dict] = []

            # 前缀提取
            for pattern_str in prefix_patterns:
                try:
                    pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                    while True:
                        match = pattern.match(current_text)
                        if match:
                            prefix_text = match.group(0)
                            current_prefixes.append({"prefix": prefix_text, "pattern": pattern_str})
                            current_text = current_text[len(prefix_text):]
                        else:
                            break
                except re.error as e:
                    print(f"[Warning]: 前缀正则匹配出现问题！！  Regex error for prefix pattern '{pattern_str}' on key '{key}': {e}")
                    continue

            # 后缀提取
            for pattern_str in suffix_patterns:
                try:
                    pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                    # 需要循环查找，因为移除一个后缀后，可能又有新的后缀匹配在末尾
                    made_change = True
                    while made_change:
                        made_change = False
                        # 从后向前查找匹配似乎更稳妥，但 re 不直接支持
                        # 使用 finditer 找到所有匹配，然后检查最后一个是否在末尾
                        best_match = None
                        for match in pattern.finditer(current_text):
                            if match.end() == len(current_text):
                                best_match = match # 找到一个末尾匹配

                        if best_match:
                            suffix_text = best_match.group(0)
                            current_suffixes.insert(0, {"suffix": suffix_text, "pattern": pattern_str})
                            current_text = current_text[:best_match.start()]
                            made_change = True # 成功移除，需要再次检查

                except re.error as e:
                    print(f"[Warning]: 后缀正则匹配出现问题！！  Regex error for suffix pattern '{pattern_str}' on key '{key}': {e}")
                    continue


            # 空文本检查(避免提取完前后缀只剩下空白)
            if not current_text.strip(): # 检查是否只剩下空白
                 # 如果提取后文本为空或只有空白，则尝试恢复
                temp_prefix_str = ''.join([p['prefix'] for p in current_prefixes])
                temp_suffix_str = ''.join([s['suffix'] for s in current_suffixes])

                # 简单的恢复逻辑：如果只有前缀或只有后缀，恢复它。如果都有，恢复较短者。
                if current_prefixes and current_suffixes:
                    prefix_len = sum(len(p['prefix']) for p in current_prefixes)
                    suffix_len = sum(len(s['suffix']) for s in current_suffixes)

                    if prefix_len > suffix_len:
                        current_text = current_text + temp_suffix_str # 恢复后缀
                        current_suffixes = [] # 清空记录
                    else:
                        current_text = temp_prefix_str + current_text # 恢复前缀
                        current_prefixes = [] # 清空记录

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
            # 还原前缀：按记录顺序拼接
            prefix_str = ''.join([item['prefix'] for item in prefix_codes.get(key, [])])
            # 还原后缀：按记录顺序拼接 (因为记录时是 insert(0,...)，所以直接 join 就是正确的顺序)
            suffix_str = ''.join([item['suffix'] for item in suffix_codes.get(key, [])])

            restored = f"{prefix_str}{text}{suffix_str}"
            restored_dict[key] = restored

        return restored_dict


    # 译前替换
    def replace_before_translation(self, config, text_dict: dict) -> dict:
        """
        在翻译前根据配置规则替换文本。优先使用正则表达式。

        Args:
            config: 包含 pre_translation_data 列表的配置对象。
            text_dict: 包含待处理文本的字典 {id: text}。

        Returns:
            处理后的 text_dict。
        """

        data: list[dict] = config.pre_translation_data or [] # 确保 data 是列表

        # 创建一个新的字典来存储结果，避免在迭代时修改原始字典
        processed_text_dict = text_dict.copy()

        for k in processed_text_dict:
            original_text = processed_text_dict[k]
            current_text = original_text

            for i, rule in enumerate(data):
                regex_pattern = rule.get("regex")
                src_text = rule.get("src")
                dst_text = rule.get("dst", "") # 默认为空字符串，用于删除

                # --- 优先处理正则表达式 ---
                if regex_pattern:
                    # 使用 re.sub 进行正则替换
                    # re.sub 会替换所有匹配项
                    new_text = re.sub(regex_pattern, dst_text, current_text)
                    if new_text != current_text:
                        current_text = new_text

                    continue # 继续处理下一条规则

                # --- 如果没有正则表达式或正则未执行，处理 src 文本替换 ---
                elif src_text:
                    # 只有当 regex 字段不存在或为空时，才执行 src 替换
                    if src_text in current_text:
                        new_text = current_text.replace(src_text, dst_text)
                        current_text = new_text

            # 更新字典中的值
            if current_text != original_text:
                 processed_text_dict[k] = current_text

        return processed_text_dict

    # 译后替换
    def replace_after_translation(self, config, text_dict: dict) -> dict:
        """
        在翻译后根据配置规则替换文本。优先使用正则表达式。

        Args:
            config: 包含 post_translation_data 列表的配置对象。
            text_dict: 包含待处理文本的字典 {id: text}。

        Returns:
            处理后的 text_dict。
        """

        data: list[dict] = config.post_translation_data or [] # 确保 data 是列表

        processed_text_dict = text_dict.copy()

        for k in processed_text_dict:
            original_text = processed_text_dict[k]
            current_text = original_text

            for i, rule in enumerate(data):
                regex_pattern = rule.get("regex")
                src_text = rule.get("src")
                dst_text = rule.get("dst", "")

                # --- 优先处理正则表达式 ---
                if regex_pattern:
                    new_text = re.sub(regex_pattern, dst_text, current_text)
                    if new_text != current_text:
                        current_text = new_text
                    continue # 只要有 regex 字段就跳过 src

                # --- 如果没有正则表达式或正则未执行，处理 src 文本替换 ---
                elif src_text:
                    if src_text in current_text:
                        new_text = current_text.replace(src_text, dst_text)
                        current_text = new_text

            # 更新字典中的值
            if current_text != original_text:
                 processed_text_dict[k] = current_text

        return processed_text_dict


    # 数字序号预处理
    def digital_sequence_preprocessing(self, text_dict: dict) -> dict:

        # 数字序号处理
        for k in text_dict:
            # 匹配以数字+英文句点开头的模式，替换为【数字】
            text_dict[k] = re.sub(r'^(\d+)\.', r'【\1】', text_dict[k], count=1)

        return text_dict

    #  数字序号恢复
    def digital_sequence_recovery(self, text_dict: dict) -> dict:

        # 数字序号恢复
        for k in text_dict:
            # 匹配以【数字】开头的模式，恢复为数字+英文句点
            text_dict[k] = re.sub(r'^【(\d+)】', r'\1.', text_dict[k], count=1)

        return text_dict

    # 预提取前后缀的空格与换行
    def strip_and_record_affix_whitespace(self, text_dict):
        r"""
        预处理字典中的文本值，移除前后缀的空白字符（空格、换行等），
        并将移除的信息存储在另一个字典中。

        Args:
            text_dict (dict): 输入的字典，键为标识符，值为包含潜在前后缀空白的字符串。
                            例如：{'0': '\n  text  \n'}

        Returns:
            tuple: 包含两个字典的元组：
            - processed_text_dict (dict): 处理后的字典，值的文本变得“干净”。
                                            例如：{'0': 'text'}
            - processing_info (dict): 存储了每个键对应的前后缀信息的字典。
                                        例如：{'0': {'prefix': '\n  ', 'suffix': '  \n'}}
        """
        processed_text_dict = {}
        processing_info = {}
        # 正则表达式：匹配开头的空白字符(^(\s*))，中间的任意字符(.*?)，结尾的空白字符((\s*)$)
        # re.DOTALL 让 '.' 可以匹配换行符
        pattern = re.compile(r'^(\s*)(.*?)(\s*)$', re.DOTALL)

        for key, original_text in text_dict.items():
            if not isinstance(original_text, str):
                # 如果值不是字符串，可以选择跳过、报错或原样保留
                # 这里选择原样保留，并且不记录处理信息
                processed_text_dict[key] = original_text
                continue

            match = pattern.match(original_text)
            if match:
                prefix = match.group(1)  # 捕获的前缀空白
                core_text = match.group(2) # 捕获的中间“干净”文本
                suffix = match.group(3)  # 捕获的后缀空白

                processed_text_dict[key] = core_text
                processing_info[key] = {
                    'prefix': prefix, 
                    'suffix': suffix
                }
            else:
                # 理论上，上面的正则应该能匹配所有字符串，包括空字符串
                # 但为了健壮性，可以加个处理（虽然在这个模式下不太可能进入）
                processed_text_dict[key] = original_text # 原样保留
                processing_info[key] = {'prefix': '', 'suffix': ''} # 记录为空白

        return processed_text_dict, processing_info

    # 还原前后缀的空格与换行
    def restore_affix_whitespace(self, processing_info, processed_dict):
        r"""
        根据预处理时存储的信息，将前后缀空白还原到处理后的（可能已翻译的）文本字典中。

        Args:
            processed_dict (dict): 经过预处理（且可能已翻译）的字典。
                                例如：{'0': 'translated text'}
            processing_info (dict): 包含原始前后缀信息的字典。
                                    例如：{'0': {'prefix': '\n  ', 'suffix': '  \n'}}

        Returns:
            dict: 还原了前后缀空白的最终字典。
                例如：{'0': '\n  translated text  \n'}
        """
        restored_text_dict = {}

        for key, core_text in processed_dict.items():
            if key in processing_info:
                info = processing_info[key]
                prefix = info.get('prefix', '') # 安全获取，如果键不存在则返回空字符串
                suffix = info.get('suffix', '') # 安全获取
                restored_text_dict[key] = prefix + core_text + suffix
            else:
                # 如果某个键在处理信息中不存在（可能在翻译过程中新增或删除了条目）
                # 则直接保留处理后的文本，不添加前后缀
                restored_text_dict[key] = core_text

        return restored_text_dict



