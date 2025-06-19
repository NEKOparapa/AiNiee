

import re


class FormatExtractor:

    def text_extraction(self, html_string):
        """
        从HTML字符串中提取最后一个<textarea>的内容，并将其转换为一个结构化字典。
        字典的每个条目都包含文本行内容和其后跟随的连续空行数。

        Args:
            html_string (str): 包含HTML内容的字符串。

        Returns:
            dict: 一个字典，键是内容的行号（字符串形式），值是另一个字典，
                  包含 'text' (行文本) 和 'blank_lines_after' (该行后的空行数)。
                  例如: {'0': {'text': '第一行', 'blank_lines_after': 2}, ...}
        """
        # 只提取最后一个 textarea 标签的内容
        textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', html_string, re.DOTALL)
        if not textarea_contents:
            return {}  # 如果没有找到 textarea 标签，返回空字典
        
        last_content = textarea_contents[-1]
        
        
        lines = last_content.split("\n")
        structured_data = []
        current_text_item = None

        for line in lines:
            stripped_line = line.strip()
            if stripped_line:  # 如果当前行有内容
                # 如果之前正在处理一个文本项，现在遇到了新的文本项，
                # 说明上一个文本项已经处理完毕，可以将其添加到结果列表中。
                if current_text_item:
                    structured_data.append(current_text_item)
                
                # 开始一个新的文本项
                current_text_item = {
                    'text': stripped_line, # 保存清理过的文本
                    'blank_lines_after': 0
                }
            elif current_text_item:  # 如果当前行是空行，并且前面有文本
                # 增加它前面那个文本项的“后续空行数”计数器
                current_text_item['blank_lines_after'] += 1

        # 循环结束后，不要忘记添加最后一个正在处理的文本项
        if current_text_item:
            structured_data.append(current_text_item)
            
        # 如果没有提取到任何有效内容，返回空字典
        if not structured_data:
            return {}

        # 将列表转换为带行号的字典
        format_result_dict = {str(i): item for i, item in enumerate(structured_data)}
        
        return format_result_dict