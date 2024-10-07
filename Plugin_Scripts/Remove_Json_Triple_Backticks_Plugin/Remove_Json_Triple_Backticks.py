from ..Plugin_Base.Plugin_Base import PluginBase


class Remove_Json_Triple_Backticks(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "remove_json_triple_backticks_Plugin"
        self.description = "This is an remove_json_triple_backticks plugin."

    def load(self):
        print(f"[INFO]  {self.name} loaded!")


    def on_event(self, event_name, configuration_information, event_data):

        # 文本预处理事件触发
        if event_name == "complete_text_process":

            text = self.remove_json_triple_backticks(event_data)

        return text



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