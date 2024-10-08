import re

from .TextHelper import TextHelper
from ..Plugin_Base.Plugin_Base import PluginBase

class Non_Japanese_Korean_Text_Filtering(PluginBase):
    
    def __init__(self):
        super().__init__()
        self.name = "Non_Japanese_Korean_Text_Filtering_Plugin"
        self.description = "This is an example plugin."

    def load(self):
        print(f"[INFO]  {self.name} loaded!")

    def on_event(self, event_name, configuration_information, event_data):
        # 事件触发
        if event_name == "text_filter":
            if configuration_information.source_language == "日语" or configuration_information.source_language == "韩语":
                self.process_text_by_language(event_data, configuration_information.source_language)
                print(f"[INFO]  Non-Japanese/Korean text has been filtered.")

    # 根据目标语言处理缓存列表中的条目 
    def process_text_by_language(self, cache_list, language):
        if language == "日语":
            for item in cache_list:
                if not TextHelper.has_any_japanese(item.get("source_text", "")):
                    item["translation_status"] = 7

        if language == "韩语":
            for item in cache_list:
                if not TextHelper.has_any_korean(item.get("source_text", "")):
                    item["translation_status"] = 7