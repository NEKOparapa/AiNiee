from ModuleFolders.Cache.CacheItem import TranslationStatus
from ModuleFolders.Cache.CacheManager import CacheManager
from ModuleFolders.Cache.CacheProject import CacheProject
from PluginScripts.PluginBase import PluginBase


class IncrementalFilePlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "IncrementalFilePlugin"
        self.description = (
            "增量文件插件，当文件夹下新增或修改文件后，只翻译新增或修改的文件。\n"
            "注意！翻译完成后存量文件也会重新输出！"
        )

        self.visibility = True  # 是否在插件设置中显示
        self.default_enable = False  # 默认不启用

        # 为保证增量文本读取在其他插件之前，用最高优先级
        self.add_event("text_filter", PluginBase.PRIORITY.HIGHEST)

    def on_event(self, event_name, config, event_data: CacheProject):
        if event_name == "text_filter":
            self.read_incremental_files(config, event_data)

    def read_incremental_files(self, config, event_data: CacheProject):

        cache_manager = CacheManager()
        cache_manager.load_from_file(config.label_output_path)
        if not hasattr(cache_manager, "project"):
            return
        cache_files = cache_manager.project.files

        for file in event_data.files.values():
            if file.storage_path in cache_files:
                cache_line_set = set(x.source_text for x in cache_files[file.storage_path].items)
                cache_items = iter(cache_files[file.storage_path].items)  # 用迭代器代替下标

                for line in file.items:
                    # 防止中间插入的行遍历完迭代器
                    if line.source_text not in cache_line_set:
                        continue
                    for cache_line in cache_items:
                        # 在缓存中找到当前的片段
                        if cache_line.source_text == line.source_text:
                            # 更新已翻译的片段
                            if cache_line.translation_status == TranslationStatus.TRANSLATED and line.translation_status == TranslationStatus.UNTRANSLATED:
                                line.translation_status = cache_line.translation_status
                                line.model = cache_line.model
                                line.translated_text = cache_line.translated_text
                            break
