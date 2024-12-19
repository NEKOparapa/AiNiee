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


    def on_event(self, event_name, config, event_data):

        # 文本预处理事件触发
        if event_name == "complete_text_process":

            self.remove_json_triple_backticks(event_data)
            self.replace_newline(event_data)
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

    

    # 将文本中的字符型 “\n” 替换为实际的换行符
    def replace_newline(self,input_string):

        input_string.replace('\\n', '\n').replace('\\r', '\r')  #现在只能针对替换，并不能将\\替换为\
        #input_strings = re.sub(r'\\n', '\n', input_string)



