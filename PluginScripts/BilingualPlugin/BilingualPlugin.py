from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.Cache.CacheProject import CacheProject
from PluginScripts.PluginBase import PluginBase


class BilingualPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "BilingualPlugin"
        self.description = "双语对照插件"+ "\n"+ "最后输出的翻译内容会是【译文+换行符+原文】的双语组合，请谨慎开启。\nSRT、EPUB和TXT文件会默认输出译文与双语版本，请不要开启该插件" 

        self.visibility = True  # 是否在插件设置中显示
        self.default_enable = False  # 默认启用状态

        self.add_event("postprocess_text", PluginBase.PRIORITY.LOWEST)  # 添加感兴趣的事件和优先级
        self.add_event("manual_export", PluginBase.PRIORITY.LOWEST)

    def load(self):
        pass

    def on_event(self, event_name, config, event_data: CacheProject):
        if event_name in ("manual_export", "postprocess_text"):
            self.process_dictionary_list(event_data)

    def process_dictionary_list(self, event_data: CacheProject):
        for entry in event_data.items_iter():

            source_text = entry.source_text
            translated_text = entry.translated_text
            translation_status = entry.translation_status

            if translation_status == TranslationStatus.TRANSLATED:
                entry.translated_text = translated_text + "\n" + source_text
