from ..Plugin_Base.Plugin_Base import PluginBase



class Bilingual_Comparison(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "Bilingual_Comparison_Plugin"
        self.description = "This is an Bilingual_Comparison plugin."

    def load(self):
        print(f"[INFO]  {self.name} loaded!")


    def on_event(self, event_name, configuration_information, event_data):

        # 事件触发
        if event_name == "postprocess_text":

            # 构建该插件配置文件路径
            the_plugin_dir = configuration_information.plugin_dir + "\Bilingual_Comparison_Plugin"+"\config.txt" 

            # 获取配置开关
            switch = self.check_switch_status(the_plugin_dir)

            if switch:
                self.process_dictionary_list(event_data)



    def check_switch_status(self,file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                if "双语开关: 开" in content:
                    return True
                else:
                    return False
        except FileNotFoundError:
            return "文件未找到"
        except Exception as e:
            return f"读取开关文件时发生错误: {e}"


    def process_dictionary_list(self,cache_list):
        for entry in cache_list:
            
            storage_path = entry.get('storage_path')

            if storage_path:
                source_text = entry.get('source_text')
                translated_text = entry.get('translated_text')
                translation_status = entry.get('translation_status')

                if  translation_status == 1 :
                    entry['translated_text'] = source_text +"\n"+ translated_text
