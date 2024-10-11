import os
from ..Plugin_Base.Plugin_Base import PluginBase

import yaml

class Bilingual_Comparison(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "Bilingual_Comparison_Plugin"
        self.description = "This is an Bilingual_Comparison plugin."
        self.add_event('postprocess_text', 10)  # 添加感兴趣的事件和优先级


    def load(self):
        print(f"[INFO]  {self.name} loaded!")


    def on_event(self, event_name, configuration_information, event_data):

        # 事件触发
        if event_name == "postprocess_text":

            # 构建该插件配置文件路径
            the_plugin_dir = os.path.join(configuration_information.plugin_dir, "Bilingual_Comparison_Plugin", "config.yaml") 

            # 获取配置开关
            switch = self.read_yaml_switchparameter(the_plugin_dir)

            if switch:
                self.process_dictionary_list(event_data)



    def read_yaml_switchparameter(self,file_path):
        """
        读取YAML文件并返回开关参数的值。
        参数:
        file_path (str): YAML文件的路径。
        返回:
        bool: 开关参数的值。如果找不到参数，则返回None。
        """
        with open(file_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        # 假设开关参数在YAML文件中名为'switch'
        return data.get('双语开关', None)


    def process_dictionary_list(self,cache_list):
        for entry in cache_list:

            storage_path = entry.get('storage_path')

            if storage_path:
                source_text = entry.get('source_text')
                translated_text = entry.get('translated_text')
                translation_status = entry.get('translation_status')

                if  translation_status == 1 :
                    entry['translated_text'] = source_text +"\n"+ translated_text