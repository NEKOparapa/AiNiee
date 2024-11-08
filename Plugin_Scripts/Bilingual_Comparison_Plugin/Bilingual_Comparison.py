from ..PluginBase import PluginBase


class Bilingual_Comparison(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "Bilingual_Comparison_Plugin"
        self.description = "翻译完成后，输出双语对照结果"

        self.visibility = True  # 是否在插件设置中显示
        self.default_enable = False  # 默认启用状态

        self.add_event("postprocess_text", PluginBase.PRIORITY.LOWEST)  # 添加感兴趣的事件和优先级

    def load(self):
        print(f"[INFO] {self.name} loaded!")

    def on_event(self, event_name, configuration_information, event_data):
        if event_name == "postprocess_text":
            self.process_dictionary_list(event_data)

    def process_dictionary_list(self, cache_list):
        for entry in cache_list:
            storage_path = entry.get("storage_path")

            if storage_path:
                source_text = entry.get("source_text")
                translated_text = entry.get("translated_text")
                translation_status = entry.get("translation_status")

                if translation_status == 1:
                    entry["translated_text"] = source_text + "\n" + translated_text