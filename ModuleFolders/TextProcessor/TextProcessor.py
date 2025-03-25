import re
from typing import List, Dict, Tuple

from Base.Base import Base


class TextProcessor(Base):
    def __init__(self):
        pass

    # 译前文本处理
    def replace_all(self, config, text_dict: Dict[str, str], code_pattern_list):
        """执行全部替换操作"""
        processed_text = {k: v for k, v in text_dict.items()}
        prefix_codes, suffix_codes, placeholder_order = {}, {}, {}

        # 自动处理代码段
        if config.auto_process_text_code_segment:
            # 处理前后缀
            processed_text, prefix_codes, suffix_codes = TextProcessor._process_affixes(self, processed_text,code_pattern_list)

            # 特殊文本占位替换
            processed_text, placeholder_order = TextProcessor._replace_special_placeholders(self,config.target_platform,processed_text,placeholder_order,code_pattern_list)

        # 译前替换
        if config.pre_translation_switch:
            processed_text = TextProcessor.replace_before_translation(self, config, processed_text)

        # 数字序号预处理
        processed_text = TextProcessor.digital_sequence_preprocessing(self, processed_text)

        return processed_text, prefix_codes, suffix_codes, placeholder_order

    # 译后文本处理
    def restore_all(self, config, text_dict: Dict[str, str], prefix_codes: Dict, suffix_codes: Dict,placeholder_order) -> Dict[str, str]:
        """执行全部还原操作"""
        restored = text_dict.copy()

        # 自动处理代码段
        if config.auto_process_text_code_segment:
            restored = TextProcessor._restore_special_placeholders(self, restored, placeholder_order)
            restored = TextProcessor._restore_affixes(self, restored, prefix_codes, suffix_codes)

        # 译后替换
        if config.post_translation_switch:
            restored = TextProcessor.replace_after_translation(self, config, restored)

        # 数字序号恢复
        restored = TextProcessor.digital_sequence_recovery(self, restored)

        return restored

    def _replace_special_placeholders(self, target_platform, text_dict: Dict[str, str], placeholder_order,code_pattern_list) -> Dict[str, str]:
        """特殊文本占位替换"""

        # 获取并构建正则库
        placeholder_patterns = TextProcessor._build_special_placeholder_pattern(self, code_pattern_list)

        new_dict = {}
        global_match_count = 0  # 全局匹配计数器

        # 遍历每个文本条目
        for key, text in text_dict.items():
            all_placeholders: List[Dict[str, str]] = []
            updated_text = text  # 使用 updated_text 避免在循环中修改 text 导致问题

            sakura_match_count = 0  # sakura匹配计数器

            # 遍历每个正则
            for pattern_str in placeholder_patterns:
                if global_match_count >= 30:  # 全局匹配次数达到上限，停止所有替换，避免因为正则错误而全部替换
                    break  

                pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                match = pattern.search(updated_text) # 使用 search 查找第一个匹配项

                if match: # 如果找到匹配项
                    global_match_count += 1 # 全局占位符数共用比单行占位符数共用，AI回复稳定性高
                    sakura_match_count += 1 # 全Sakura专用，反之

                    original = match.group(0)
                    if target_platform == "sakura":
                        # Sakura 平台使用下箭头，并根据 sakura_match_count 增加数量
                        placeholder = "↓" * sakura_match_count
                    else:
                        # 其他平台使用原始的占位符格式
                        placeholder = f"""{{_PLACEHOLDER{global_match_count}_}}"""

                    # 记录占位符和原始文本的映射关系
                    all_placeholders.append({
                        "placeholder": placeholder,
                        "original": original,
                        "pattern": pattern_str # 记录触发的pattern
                    })

                    # 执行替换，只替换第一个匹配项
                    start, end = match.span()
                    updated_text = updated_text[:start] + placeholder + updated_text[end:]


            placeholder_order[key] = all_placeholders # 存储所有 pattern 的替换结果
            new_dict[key] = updated_text # 使用 updated_text

        return new_dict, placeholder_order

    def _build_special_placeholder_pattern(self, code_pattern_list) -> List[str]:
        r"""构建特殊占位符匹配的正则表达式 列表
        注意：
        对于 \\\\. 模式，增强后的正则变为 \s*\\\\.\s*，这会匹配反斜杠前后可能的空白（包括换行符 \n）。
        如果文本中的反斜杠附近存在换行符（例如 ...\.\n...），增强后的正则会连带匹配到 \n。
        """
        enhanced_patterns = []
        for p in code_pattern_list:
            enhanced = fr"\s*{p}\s*"
            enhanced_patterns.append(enhanced)
        return enhanced_patterns

    def _restore_special_placeholders(self, text_dict: Dict[str, str], placeholder_order) -> Dict[str, str]:
        """占位符还原"""

        new_dic = {}

        for key, text in text_dict.items():
            placeholders = placeholder_order.get(key, [])

            if not placeholders:
                new_dic[key] = text

            else:
                for item in reversed(placeholders):  # 反序循环，主要是为了兼容Sakura
                    placeholder_text = item.get("placeholder")
                    original_text = item.get("original")

                    text = text.replace(placeholder_text, original_text, 1) # 每次只替换一个

                new_dic[key] = text

        return new_dic

    def _process_affixes(self, text_dict: Dict[str, str], code_pattern_list) -> Tuple[Dict[str, str], Dict, Dict]:
        """处理前后缀提取"""
        prefix_codes = {}
        suffix_codes = {}

        prefix_patterns, suffix_patterns = TextProcessor._build_affixes_patterns(self, code_pattern_list)

        for key, text in text_dict.items():
            current_prefixes: List[Dict] = []
            current_suffixes: List[Dict] = []

            # 前缀提取（保留原始空白）
            for pattern_str in prefix_patterns:
                pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                while True: # 循环应用当前 pattern，直到没有匹配到前缀
                    match = pattern.match(text) # 匹配字符串的开头
                    if match:
                        prefix_text = match.group(0)
                        current_prefixes.append({"prefix": prefix_text, "pattern": pattern_str}) # 记录 prefix 和 pattern
                        text = text[len(prefix_text):] # 移除匹配到的前缀部分
                    else:
                        break # 当前 pattern 没有匹配到前缀，跳出内循环
            prefix_codes[key] = current_prefixes


            # 后缀提取（保留原始空白）
            for pattern_str in suffix_patterns:
                pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                while True: # 循环应用当前 pattern，直到没有匹配到后缀
                    match = pattern.search(text) # 搜索字符串的任意位置
                    if match and match.end() == len(text): # 匹配的后缀必须在字符串的末尾
                        suffix_text = match.group(0)
                        current_suffixes.insert(0, {"suffix": suffix_text, "pattern": pattern_str}) # 记录 suffix 和 pattern, 插入到列表开头保持顺序
                        text = text[:match.start()] # 移除匹配到的后缀部分
                    else:
                        break # 当前 pattern 没有匹配到后缀，跳出内循环
            suffix_codes[key] = current_suffixes


            # 检查中间文本是否为空,避免提取完前后缀后内容为空（暂时解决方法）
            if not text:
                has_prefix = len(current_prefixes) > 0
                has_suffix = len(current_suffixes) > 0

                if has_prefix and has_suffix:
                    # 比较总字符长度
                    prefix_len = sum(len(p['prefix']) for p in current_prefixes)
                    suffix_len = sum(len(s['suffix']) for s in current_suffixes)

                    if prefix_len <= suffix_len:
                        # 还原前缀并清空
                        text = ''.join([p['prefix'] for p in current_prefixes])
                        prefix_codes[key] = []
                    else:
                        # 还原后缀并清空
                        text = ''.join([s['suffix'] for s in current_suffixes])
                        suffix_codes[key] = []
                elif has_prefix:
                    # 仅还原前缀
                    text = ''.join([p['prefix'] for p in current_prefixes])
                    prefix_codes[key] = []
                elif has_suffix:
                    # 仅还原后缀
                    text = ''.join([s['suffix'] for s in current_suffixes])
                    suffix_codes[key] = []


            text_dict[key] = text

        return text_dict, prefix_codes, suffix_codes

    def _restore_affixes(self, text_dict: Dict[str, str], prefix_codes: Dict, suffix_codes: Dict) -> Dict[str, str]:
        """还原前后缀"""
        restored_dict = {}
        for key in text_dict:
            prefix_str = ''.join([item['prefix'] for item in prefix_codes.get(key, [])])
            suffix_str = ''.join([item['suffix'] for item in suffix_codes.get(key, [])])

            restored = f"{prefix_str}{text_dict[key]}{suffix_str}"
            restored_dict[key] = restored

        return restored_dict


    def _build_affixes_patterns(self, code_pattern_list) -> Tuple[List[str], List[str]]:
        """构建前后缀正则表达式对象 列表"""
        if not code_pattern_list:
            return [], []

        # 为每个模式添加前后空白换行匹配能力
        enhanced_patterns = []
        for p in code_pattern_list:
            enhanced = fr"\s*{p}\s*"
            enhanced_patterns.append(enhanced)

        return enhanced_patterns, enhanced_patterns # 前后缀pattern列表相同


    # 译前替换
    def replace_before_translation(self, config, text_dict: dict) -> dict:
        data: list[dict] = config.pre_translation_data

        for k in text_dict:
            for v in data:
                if v.get("src", "") in text_dict[k]:
                    text_dict[k] = text_dict[k].replace(v.get("src", ""), v.get("dst", ""))

        return text_dict

    # 译后替换
    def replace_after_translation(self,config, text_dict: dict) -> dict:
        data: list[dict] = config.post_translation_data

        for k in text_dict:
            for v in data:
                if v.get("src", "") in text_dict[k]:
                    text_dict[k] = text_dict[k].replace(v.get("src", ""), v.get("dst", ""))

        return text_dict


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




