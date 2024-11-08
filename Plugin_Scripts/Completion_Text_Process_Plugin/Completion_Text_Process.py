import re
from ..PluginBase import PluginBase


class Completion_Text_Process_Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "Completion_Text_Process_Plugin"
        self.description = "This is an Completion_Text_Process_Plugin."

        self.visibility = False # 是否在插件设置中显示
        self.default_enable = True # 默认启用状态

        self.add_event('complete_text_process', PluginBase.PRIORITY.NORMAL)

    def load(self):
        print(f"[INFO] {self.name} loaded!")


    def on_event(self, event_name, configuration_information, event_data):

        # 文本预处理事件触发
        if event_name == "complete_text_process":

            event_data = self.remove_json_triple_backticks(event_data)
            #text = self.repair_double_quotes_2(text)




    # 清除文本开头结尾的代码块标记
    def remove_json_triple_backticks(self,s):
        """
        移除字符串开头的"```json"和结尾的"```"。

        参数:
        s (str): 输入字符串。

        返回:
        str: 处理后的字符串。
        """
        if not isinstance(s, str):
            raise ValueError("Input must be a string")

        start_len = len("```json")
        end_len = len("```")

        if s.startswith("```json"):
            s = s[start_len:]
        if s.endswith("```"):
            s = s[:-end_len]

        return s
    # 修复value前面的双引号(存在文本开头是空格，而错误添加的问题)
    def repair_double_quotes(self,text):

        # 正则表达式匹配双引号后跟冒号，并捕获第三个字符
        pattern = r'[\"]:(.)'
        # 使用finditer来找到所有匹配项
        matches = re.finditer(pattern, text)
        # 存储所有修改的位置
        modifications = [(match.start(1), match.group(1)) for match in matches]

        # 从后往前替换文本，这样不会影响后续匹配的位置
        for start, char in reversed(modifications):
            if char != '"':
                text = text[:start] + '"' + text[start:]

        return text

    # 修复value后面的双引号
    def repair_double_quotes_2(self,text):

        # 正则表达式匹配逗号后面跟换行符（可选）,再跟双引号的模式
        pattern = r',(?:\n)?\"'
        matches = re.finditer(pattern, text)
        result = []

        last_end = 0
        for match in matches:
            # 获取逗号前的字符
            quote_position = match.start()
            before_quote = text[quote_position - 1]

            # 检查逗号前的字符是否是双引号
            if before_quote == '"':
                # 如果是双引号，将这一段文本加入到结果中
                result.append(text[last_end:quote_position])
            else:
                # 如果不是双引号，将前一个字符换成'"'
                result.append(text[last_end:quote_position - 1] + '"')

            # 更新最后结束的位置
            last_end = quote_position

        # 添加剩余的文本
        result.append(text[last_end:])

        # 将所有片段拼接起来
        return ''.join(result)

    # 修复大括号前面的双引号
    def repair_double_quotes_3(self,text):

        # 正则表达式匹配逗号后面紧跟双引号的模式
        pattern = r'(?:\n)?}'
        matches = re.finditer(pattern, text)
        result = []

        last_end = 0
        for match in matches:
            # 获取逗号前的字符
            quote_position = match.start()
            before_quote = text[quote_position - 1]

            # 检查逗号前的字符是否是双引号
            if before_quote == '"':
                # 如果是双引号，将这一段文本加入到结果中
                result.append(text[last_end:quote_position])
            else:
                # 如果不是双引号，将前一个字符换成'"'
                result.append(text[last_end:quote_position - 1] + '"')

            # 更新最后结束的位置
            last_end = quote_position

        # 添加剩余的文本
        result.append(text[last_end:])

        # 将所有片段拼接起来
        return ''.join(result)