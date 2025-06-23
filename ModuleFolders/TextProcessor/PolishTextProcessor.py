import re
from typing import List, Dict, Optional, Any

# 与TextProcessor基本一样
class PolishTextProcessor():

    # 数字序号处理的正则表达式
    RE_DIGITAL_SEQ_PRE_STR = r'^(\d+)\.'
    RE_DIGITAL_SEQ_REC_STR = r'^【(\d+)】'

    def __init__(self, config: Any):
        super().__init__()

        # 预编译固定处理的正则表达式
        self.RE_DIGITAL_SEQ_PRE = re.compile(self.RE_DIGITAL_SEQ_PRE_STR)
        self.RE_DIGITAL_SEQ_REC = re.compile(self.RE_DIGITAL_SEQ_REC_STR)

        # 预编译文本前后替换规则
        self.pre_translation_rules_compiled = self._compile_translation_rules(
            getattr(config, 'pre_translation_data', None)
        )
        self.post_translation_rules_compiled = self._compile_translation_rules(
            getattr(config, 'post_translation_data', None)
        )

    def _compile_translation_rules(self, rules_data: Optional[List[Dict]]) -> List[Dict]:
        """
        编译翻译替换规则，将规则中的正则表达式字符串预编译成 re.Pattern 对象。
        """
        compiled_rules = []
        if not rules_data:
            return compiled_rules

        for rule in rules_data:
            new_rule = rule.copy()
            # 如果规则中包含 "regex" 键，则进行编译
            if regex_str := rule.get("regex"):
                try:
                    new_rule["compiled_regex"] = re.compile(regex_str)
                except re.error as e:
                    print(f"警告：编译正则表达式 '{regex_str}' 时出错: {e}")
            compiled_rules.append(new_rule)
        return compiled_rules

    # 译前替换处理
    def replace_before_translation(self, text_dict: Dict[str, str]) -> Dict[str, str]:
        """
        根据预设规则，在翻译前对文本进行批量替换。
        支持普通字符串替换和正则表达式替换。
        """
        processed_text_dict = {}
        for k, original_text in text_dict.items():
            current_text = original_text
            # 遍历所有预编译的译前规则
            for rule in self.pre_translation_rules_compiled:
                compiled_regex = rule.get("compiled_regex")
                src_text = rule.get("src")
                dst_text = rule.get("dst", "")

                if compiled_regex:
                    current_text = compiled_regex.sub(dst_text, current_text)
                elif src_text and src_text in current_text:
                    current_text = current_text.replace(src_text, dst_text)
            
            processed_text_dict[k] = current_text
        return processed_text_dict

    # 译后替换处理
    def replace_after_translation(self, text_dict: Dict[str, str]) -> Dict[str, str]:
        """
        根据预设规则，在翻译后对文本进行批量替换。
        支持普通字符串替换和正则表达式替换。
        """
        processed_text_dict = {}
        for k, original_text in text_dict.items():
            current_text = original_text
            # 遍历所有预编译的译后规则
            for rule in self.post_translation_rules_compiled:
                compiled_regex = rule.get("compiled_regex")
                src_text = rule.get("src")
                dst_text = rule.get("dst", "")

                if compiled_regex:
                    current_text = compiled_regex.sub(dst_text, current_text)
                elif src_text and src_text in current_text:
                    current_text = current_text.replace(src_text, dst_text)

            processed_text_dict[k] = current_text
        return processed_text_dict

    # 处理数字序列
    def digital_sequence_preprocessing(self, text_dict: Dict[str, str]) -> Dict[str, str]:
        """
        将每行开头的 "数字." 格式替换为 "【数字】"，以保护其在翻译过程中不被破坏。
        """
        processed_dict = {}
        for k, text in text_dict.items():
            # 使用 sub 进行替换，count=1 确保只替换行首的第一个匹配项
            processed_dict[k] = self.RE_DIGITAL_SEQ_PRE.sub(r'【\1】', text, count=1)
        return processed_dict

    # 还原数字序列
    def digital_sequence_recovery(self, text_dict: Dict[str, str]) -> Dict[str, str]:
        """
        将 "【数字】" 格式还原为原始的 "数字." 格式。
        """
        processed_dict = {}
        for k, text in text_dict.items():
            # 使用 sub 进行还原，count=1 确保只还原行首的第一个匹配项
            processed_dict[k] = self.RE_DIGITAL_SEQ_REC.sub(r'\1.', text, count=1)
        return processed_dict

    # 译前文本处理
    def replace_all(self, config, text_dict: Dict[str, str]):
        # 存储处理后信息的变量
        processed_text = {k: v for k, v in text_dict.items()}

        # 获取各个配置信息,减少再次传递
        pre_translation_switch = config.pre_translation_switch

        # 译前替换
        if pre_translation_switch:
            processed_text = self.replace_before_translation(processed_text)

        # 处理数字序号
        processed_text = self.digital_sequence_preprocessing(processed_text)

        return processed_text

    # 译后文本处理
    def restore_all(self, config, text_dict):
        restored = text_dict.copy()

        # 获取各个配置信息
        post_translation_switch = config.post_translation_switch

        # 译后替换
        if post_translation_switch:
            restored = self.replace_after_translation(restored)

        # 数字序号还原
        restored = self.digital_sequence_recovery(restored)

        return restored
