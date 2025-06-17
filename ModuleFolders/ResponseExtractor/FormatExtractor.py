

import re


class FormatExtractor:


    # 辅助函数，正则提取标签文本内容
    def text_extraction(self,html_string):

        # 只提取最后一个 textarea 标签的内容
        textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', html_string, re.DOTALL)
        if not textarea_contents:
            return {}  # 如果没有找到 textarea 标签，返回空字典
        last_content = textarea_contents[-1]

        # 转换成字典
        format_result_dict = {}
        line_number = 0
        lines = last_content.split("\n")
        for line in lines:
            if line and line.strip():
                format_result_dict[str(line_number)] = line
                line_number += 1

        if not format_result_dict:
            return {}
        
        return format_result_dict