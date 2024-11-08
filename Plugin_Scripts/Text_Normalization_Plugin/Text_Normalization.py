from ..PluginBase import PluginBase

import jaconv # 日文文本转换工具
import unicodedata


class Text_Normalization_Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "Text_Normalization_Plugin"
        self.description = "文本规范化插件（仅支持 英文、日文 项目）"

        self.visibility = True # 是否在插件设置中显示
        self.default_enable = True # 默认启用状态

        self.add_event('normalize_text', PluginBase.PRIORITY.NORMAL)


    def load(self):
        print(f"[INFO] {self.name} loaded!")


    def on_event(self, event_name, configuration_information, event_data):

        # 事件触发
        if event_name == "normalize_text":

            # 将半角（半角假名）片假名转换为全角（全角假名）片假名
            # 全角（全角）ASCII字符和数字转换为半角（半角）ASCII字符和数字。
            # 此外，全角波浪号（～）等也被规范化。
            if configuration_information.source_language == "日语":
                for k in event_data.keys():
                    text = jaconv.normalize(event_data.get(k, ""), mode = "NFKC")
                    text = self.remove_spaces(text)
                    event_data[k] = text

            if configuration_information.source_language == "英语":
                for k in event_data.keys():
                    text = unicodedata.normalize('NFKC', event_data.get(k, ""))
                    event_data[k] = text



    def remove_spaces(self, text):
        """
        Remove both full-width and half-width spaces from the input text.
        """
        # Full-width space character
        full_width_space = '　'
        # Half-width space character
        half_width_space = ' '

        # Remove full-width spaces
        text = text.replace(full_width_space, '')
        # Remove half-width spaces
        text = text.replace(half_width_space, '')

        return text