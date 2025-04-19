from itertools import groupby

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheManager import CacheManager
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

    def on_event(self, event_name, config, event_data):
        if event_name == "text_filter":
            self.read_incremental_files(config, event_data)

    def read_incremental_files(self, config, event_data):

        cache_manager = CacheManager()
        cache_manager.load_from_file(config.label_output_path)

        cache_event_dict = {}

        # groupby需要key有序，storage_path本身有序，不需要重排
        for k, v in groupby(cache_manager.items, lambda x: x.storage_path):
            cache_item_list = list(v)
            cache_line_set = set(x.source_text for x in cache_item_list)
            cache_event_dict[k] = (cache_line_set, iter(cache_item_list))  # 用迭代器代替下标

        for line in event_data:
            if line.get('storage_path') in cache_event_dict:

                cache_line_set, cache_items = cache_event_dict[line['storage_path']]
                # 防止中间插入的行遍历完迭代器
                if line.get('source_text', '') not in cache_line_set:
                    continue
                for cache_line in cache_items:

                    # 在缓存中找到当前的片段
                    if cache_line.source_text == line.get('source_text', ''):

                        # 更新已翻译的片段
                        if cache_line.translation_status == CacheItem.STATUS.TRANSLATED:
                            line['translation_status'] = cache_line.translation_status
                            line['model'] = cache_line.model
                            line['translated_text'] = cache_line.translated_text
                        break
