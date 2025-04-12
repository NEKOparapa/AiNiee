from ..PluginBase import PluginBase


class TextLayoutRepairPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "TextLayoutRepairPlugin"
        self.description = "文本排版修复插件"+ "\n"+ "根据原文进行恢复，译文中缺失的前导空格与「」『』" 

        self.visibility = True  # 是否在插件设置中显示
        self.default_enable = False  # 默认启用状态

        self.add_event("postprocess_text", PluginBase.PRIORITY.LOWEST)  # 添加感兴趣的事件和优先级
        self.add_event("manual_export", PluginBase.PRIORITY.LOWEST)

    def load(self):
        pass

    def on_event(self, event_name, config, event_data):
        if event_name in ("manual_export", "postprocess_text"):
            self.process_dictionary_list(event_data)

    def process_dictionary_list(self, cache_list):
        for entry in cache_list:
            storage_path = entry.get("storage_path")

            if storage_path:
                source_text = entry.get("source_text")
                translated_text = entry.get("translated_text")
                translation_status = entry.get("translation_status")

                if translation_status == 1:
                    entry["translated_text"] = self.fix_typography(source_text, translated_text)



    # 排版修复算法，改进点：文本内有多个嵌套「」时，无法正常处理，需改进合并规则
    def fix_typography(self,original_text: str, translated_text: str) -> str:
        """
        修复译文的排版，使其匹配原文的某些排版特征。

        1.  将原文的前后缀空白移植到译文。
        2.  如果原文包含「，则将译文中第一个"或“替换为「。
        3.  如果原文包含」，则将译文中最后一个"或”替换为」。

        Args:
            original_text: 原始文本字符串。
            translated_text: 需要修复排版的译文文本字符串。

        Returns:
            修复排版后的译文文本字符串。
        """

        if not isinstance(original_text, str) or not isinstance(translated_text, str):
            raise TypeError("Input arguments must be strings.")

        # --- 1. 处理前后缀空白 ---

        # 记录原始文本长度
        original_len = len(original_text)

        # 获取原文前缀空白
        stripped_leading = original_text.lstrip()
        leading_whitespace_len = original_len - len(stripped_leading)
        leading_whitespace = original_text[:leading_whitespace_len]

        # 获取原文后缀空白
        stripped_trailing = original_text.rstrip()
        trailing_whitespace_len = original_len - len(stripped_trailing)
        # 检查长度>0，避免在空字符串或全空白字符串上切片出错
        if trailing_whitespace_len > 0:
            trailing_whitespace = original_text[-trailing_whitespace_len:]
        else:
            trailing_whitespace = ""

        # 清理译文前后空白，并应用原文的前后缀空白
        # 使用 strip() 清除译文原有的前后空白
        result = leading_whitespace + translated_text.strip() + trailing_whitespace

        # --- 2. 检查并替换左引号「 ---
        # 条件：原文存在「，且译文存在"或“
        if '「' in original_text and ('「' not in translated_text):
            # 查找第一个"或“的位置
            first_double_quote_index = result.find('"')
            first_opening_quote_index = result.find('“')

            # 确定要替换的引号及其位置 (选择最左边的)
            replace_index = -1
            if first_double_quote_index != -1 and first_opening_quote_index != -1:
                # 两者都存在，取索引较小的（更靠左）
                replace_index = min(first_double_quote_index, first_opening_quote_index)
            elif first_double_quote_index != -1:
                # 只有 " 存在
                replace_index = first_double_quote_index
            elif first_opening_quote_index != -1:
                # 只有 “ 存在
                replace_index = first_opening_quote_index

            # 如果找到了需要替换的引号，执行替换 (只替换第一个)
            if replace_index != -1:
                result = result[:replace_index] + '「' + result[replace_index + 1:]


        # --- 3. 检查并替换右引号」 ---
        # 条件：原文存在」，且译文存在"或”
        if '」' in original_text('」' not in translated_text):
            # 查找最后一个"或”的位置 (注意右引号是 ”)
            last_double_quote_index = result.rfind('"')
            last_closing_quote_index = result.rfind('”')

            # 确定要替换的引号及其位置 (选择最右边的)
            replace_index = -1
            if last_double_quote_index != -1 and last_closing_quote_index != -1:
                # 两者都存在，取索引较大的（更靠右）
                replace_index = max(last_double_quote_index, last_closing_quote_index)
            elif last_double_quote_index != -1:
                # 只有 " 存在
                replace_index = last_double_quote_index
            elif last_closing_quote_index != -1:
                # 只有 ” 存在
                replace_index = last_closing_quote_index

            # 如果找到了需要替换的引号，执行替换 (只替换最后一个)
            if replace_index != -1:
                result = result[:replace_index] + '」' + result[replace_index + 1:]


        # --- 4. 检查并替换左引号『 --- 
        # 条件：原文存在『，译文尚无『，且译文存在 " 或 “
        if '『' in original_text and '『' not in result:
            # 查找第一个 " 或 “ 的位置
            first_double_quote_index = result.find('"')
            first_opening_quote_index = result.find('“')

            # 确定要替换的引号及其位置 (选择最左边的)
            replace_index = -1
            if first_double_quote_index != -1 and first_opening_quote_index != -1:
                replace_index = min(first_double_quote_index, first_opening_quote_index)
            elif first_double_quote_index != -1:
                replace_index = first_double_quote_index
            elif first_opening_quote_index != -1:
                replace_index = first_opening_quote_index

            # 如果找到了需要替换的引号，执行替换 (只替换第一个)
            if replace_index != -1:
                result = result[:replace_index] + '『' + result[replace_index + 1:]

        # --- 5. 检查并替换右引号』 --- 
        # 条件：原文存在』，译文尚无』，且译文存在 " 或 ”
        if '』' in original_text and '』' not in result:
            # 查找最后一个 " 或 ” 的位置
            last_double_quote_index = result.rfind('"')
            last_closing_quote_index = result.rfind('”')

            # 确定要替换的引号及其位置 (选择最右边的)
            replace_index = -1
            if last_double_quote_index != -1 and last_closing_quote_index != -1:
                replace_index = max(last_double_quote_index, last_closing_quote_index)
            elif last_double_quote_index != -1:
                replace_index = last_double_quote_index
            elif last_closing_quote_index != -1:
                replace_index = last_closing_quote_index

            # 如果找到了需要替换的引号，执行替换 (只替换最后一个)
            if replace_index != -1:
                result = result[:replace_index] + '』' + result[replace_index + 1:]



        return result