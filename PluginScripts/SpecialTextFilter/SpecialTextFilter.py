import re
from typing import Iterator

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject, ProjectType
from ..PluginBase import PluginBase

class SpecialTextFilter(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "SpecialTextFilter"
        self.description = "SpecialTextFilter"

        self.visibility = False # 是否在插件设置中显示
        self.default_enable = True # 默认启用状态

        self.add_event('text_filter', PluginBase.PRIORITY.NORMAL)

    def load(self):
        pass


    def on_event(self, event_name, config, event_data: CacheProject):

        # 文本预处理事件触发
        if event_name == "text_filter":

            # 正对trans项目的处理
            if ProjectType.TRANS in event_data.file_project_types:

                SpecialTextFilter.filter_trans_text(self, event_data.items_iter(ProjectType.TRANS))


            # 针对MD项目的处理
            if ProjectType.MD in event_data.file_project_types:

                SpecialTextFilter.filter_md_text(self, event_data.items_iter(ProjectType.MD))

    # 特殊文本过滤器
    def filter_trans_text(self, cache_list: Iterator[CacheItem]):
        for entry in cache_list:
            tags = entry.get_extra('tags', ())
            if tags and ("red" in tags):
                entry.translation_status = CacheItem.STATUS.EXCLUED

    MD_EXCLUDE_REGEXS = (
        # 1.  ![...](http://...) and ![...](data:image...)
        re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$"),
        # 2.  ![alt][id]
        re.compile(r"^\s*!\[[^\]]*\]\[[^\]]+\]\s*$"),
        # 3.  [id]: url "title" or [id]: <url> "title"
        re.compile(r"^\s*\[[^\]]+\]:\s*<?.*>?\s*(?:(?:\".*\")|(?:'.*'))?\s*$"),
    )

    # 特殊文本过滤器
    def filter_md_text(self, cache_list: Iterator[CacheItem]):

        for entry in cache_list:
            source_text = entry.source_text

            if any(regex.match(source_text) for regex in self.MD_EXCLUDE_REGEXS):
                entry.translation_status = CacheItem.STATUS.EXCLUED
