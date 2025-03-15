import re
from typing import List, Dict, Tuple

from Base.Base import Base



class TextProcessor(Base):
    def __init__(self):
        pass

    # 译前文本处理
    def replace_all(self, config, text_dict: Dict[str, str], prefix_pattern: re.Pattern, suffix_pattern: re.Pattern,code_pattern_list, placeholder_order) :
        """执行全部替换操作"""
        processed = {k: v for k, v in text_dict.items()}
        prefix_codes, suffix_codes = {}, {}
        
        # 初始化占位符字典
        placeholder_order.clear()

        # 自动处理代码段
        if config.auto_process_text_code_segment:
            # 处理前后缀
            processed, prefix_codes, suffix_codes = TextProcessor._process_affixes(self,processed, prefix_pattern, suffix_pattern)
            
            # 新增特殊文本占位替换
            processed, placeholder_order = TextProcessor._replace_special_placeholders(self, config.target_platform,processed, placeholder_order,code_pattern_list)

        # 译前替换
        if config.pre_translation_switch:
            processed = TextProcessor.replace_before_translation(self,config, processed)

        # 数字序号预处理
        processed = TextProcessor.digital_sequence_preprocessing(self,processed)


        return processed, prefix_codes, suffix_codes,placeholder_order

    # 译后文本处理
    def restore_all(self, config, text_dict: Dict[str, str], prefix_codes: Dict, suffix_codes: Dict, placeholder_order) -> Dict[str, str]:
        """执行全部还原操作"""
        restored = text_dict.copy()

        # 自动处理代码段
        if config.auto_process_text_code_segment:
            restored = TextProcessor._restore_special_placeholders(self,restored,placeholder_order)
            restored = TextProcessor._restore_affixes(self,restored, prefix_codes, suffix_codes)

        # 译后替换
        if config.post_translation_switch:
            restored = TextProcessor.replace_after_translation(self,config, restored)

        # 数字序号恢复
        restored = TextProcessor.digital_sequence_recovery(self,restored)

        return restored

    def _replace_special_placeholders(self, target_platform, text_dict: Dict[str, str], placeholder_order,code_pattern_list) -> Dict[str, str]:
        """特殊文本占位替换

        Args:
            target_platform: 目标平台名称，例如 "sakura" 或其他
            text_dict: 包含文本的字典
        Returns:
            替换占位符后的文本字典
        """
        pattern = TextProcessor._build_special_placeholder_pattern(self,code_pattern_list)

        new_dict = {}
        for key, text in text_dict.items():
            placeholders: List[Dict[str, str]] = []
            count = 0  # 用于跟踪替换次数

            def replacer(match: re.Match) -> str:
                nonlocal count
                if count >= 5:
                    return match.group()  # 超过5次不替换

                original = match.group()
                count += 1
                if target_platform == "sakura":
                    # Sakura 平台使用下箭头，并根据 count 增加数量
                    placeholder = "↓" * count
                else:
                    # 其他平台使用原始的占位符格式
                    placeholder = f"""{{_placeholder{count}_}}"""

                # 记录占位符和原始文本的映射关系
                placeholders.append({
                    "placeholder": placeholder,
                    "original": original
                })
                return placeholder

            # 执行正则替换并保存映射关系
            processed_text = pattern.sub(replacer, text)
            placeholder_order[key] = placeholders
            new_dict[key] = processed_text

        return new_dict, placeholder_order
    

    def _build_special_placeholder_pattern(self,code_pattern_list) -> re.Pattern:
        r"""构建特殊占位符匹配的正则表达式
        注意：
        对于 \\\\. 模式，增强后的正则变为 \s*\\\\.\s*，这会匹配反斜杠前后可能的空白（包括换行符 \n）。
        如果文本中的反斜杠附近存在换行符（例如 ...\.\n...），增强后的正则会连带匹配到 \n。        
        """
        enhanced_patterns = []
        for p in code_pattern_list:
            # 若模式不包含边界或空白控制，则添加空白匹配
            if not any(c in p for c in ("^", "$", "\\s")):
                enhanced = fr"\s*{p}\s*"
            else:
                enhanced = p
            enhanced_patterns.append(enhanced)
        combined = "|".join(enhanced_patterns)
        return re.compile(combined, re.IGNORECASE | re.MULTILINE)
    

    def _restore_special_placeholders(self, text_dict: Dict[str, str],placeholder_order) -> Dict[str, str]:
        """占位符还原"""

        new_dic = {}

        for key, text in text_dict.items():
            placeholders = placeholder_order.get(key, [])
            
            if not placeholders:
                new_dic[key] = text

            else:
                for item in placeholders:
                    placeholder_text = item.get("placeholder")
                    original_text = item.get("original") 

                    text = text.replace(placeholder_text, original_text, 1)

                new_dic[key] = text
        
        # 检查未能正确替换用
        for value in new_dic.values():
            if isinstance(value, str): 
                placeholder_pattern = r'placeholder'

                if re.search(placeholder_pattern, value):
                    pass
                    #print("bug------")


        return new_dic



    def _process_affixes(self, text_dict: Dict[str, str], prefix_pat: re.Pattern, suffix_pat: re.Pattern) -> Tuple[Dict[str, str], Dict, Dict]:
        """处理前后缀提取"""
        prefixes = {}
        suffixes = {}
        
        for key, text in text_dict.items():
            # 前缀提取（保留原始空白）
            prefix_matches = []
            while (match := prefix_pat.search(text)) and match.start() == 0:
                prefix_matches.append(match.group())  # 保留原始内容（包括换行符）
                text = text[match.end():]
            prefixes[key] = prefix_matches

            # 后缀提取（保留原始空白）
            suffix_matches = []
            while (match := suffix_pat.search(text)) and match.end() == len(text):
                suffix_matches.insert(0, match.group())  # 保留原始内容
                text = text[:match.start()]
            suffixes[key] = suffix_matches

            # 检查中间文本是否为空,避免提取完前后缀后内容为空（暂时解决方法）
            if not text:
                has_prefix = len(prefix_matches) > 0
                has_suffix = len(suffix_matches) > 0

                if has_prefix and has_suffix:
                    # 比较总字符长度
                    prefix_len = sum(len(p) for p in prefix_matches)
                    suffix_len = sum(len(s) for s in suffix_matches)
                    
                    if prefix_len <= suffix_len:
                        # 还原前缀并清空
                        text = ''.join(prefix_matches)
                        prefixes[key] = []
                    else:
                        # 还原后缀并清空
                        text = ''.join(suffix_matches)
                        suffixes[key] = []
                elif has_prefix:
                    # 仅还原前缀
                    text = ''.join(prefix_matches)
                    prefixes[key] = []
                elif has_suffix:
                    # 仅还原后缀
                    text = ''.join(suffix_matches)
                    suffixes[key] = []

            text_dict[key] = text

        return text_dict, prefixes, suffixes


    def _restore_affixes(self, text_dict: Dict[str, str], prefixes: Dict, suffixes: Dict) -> Dict[str, str]:
        """还原前后缀（保留原始空白）"""
        for key in text_dict:
            # 直接拼接保留原始空白
            prefix_str = ''.join(prefixes.get(key, []))
            suffix_str = ''.join(suffixes.get(key, []))
            
            # 保留中间内容的原始前后空白
            restored = f"{prefix_str}{text_dict[key]}{suffix_str}"
            text_dict[key] = restored
            
        return text_dict


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




