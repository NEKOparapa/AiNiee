import re
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
        if event_name == "preproces_text":

            # 如果翻译日语或者韩语文本时，则去除非中日韩文本
            if  configuration_information.source_language == "日语" or  configuration_information.source_language == "韩语":

                # 过滤文本
                self.process_dictionary_list(event_data)

                print(f"[INFO]  Non-Japanese/Korean text has been filtered.")


    # 处理缓存数据的非中日韩字符，且改变翻译状态为7
    def process_dictionary_list(self,cache_list):
        pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]+')

        def contains_cjk(text):
            return bool(pattern.search(text))

        for entry in cache_list:
            source_text = entry.get('source_text')

            if isinstance(source_text, str)  and not contains_cjk(source_text):
                entry['translation_status'] = 7