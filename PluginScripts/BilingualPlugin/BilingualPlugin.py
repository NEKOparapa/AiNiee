from ..PluginBase import PluginBase


class BilingualPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "BilingualPlugin"
        self.description = "双语对照插件"+ "\n"+ "最后输出的翻译内容会是【译文+换行符+原文】的双语组合，请谨慎开启。\nSRT与EPUB文件会默认输出译文与双语版本，请不要开启该插件" 

        self.visibility = True  # 是否在插件设置中显示
        self.default_enable = False  # 默认启用状态

        self.add_event("postprocess_text", PluginBase.PRIORITY.LOWEST)  # 添加感兴趣的事件和优先级

    def load(self):
        pass

    def on_event(self, event_name, config, event_data):
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
                    entry["translated_text"] = translated_text+ "\n" + source_text