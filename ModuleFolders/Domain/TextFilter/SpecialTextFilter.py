import re
from typing import Iterator

from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import CacheProject, ProjectType


class SpecialTextFilter:
    def filter_text(self, event_data: CacheProject):

        MD_EXCLUDE_REGEXS = (
            # 1.  ![...](http://...) and ![...](data:image...)
            re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$"),
            # 2.  ![alt][id]
            re.compile(r"^\s*!\[[^\]]*\]\[[^\]]+\]\s*$"),
            # 3.  [id]: url "title" or [id]: <url> "title"
            re.compile(r"^\s*\[[^\]]+\]:\s*<?.*>?\s*(?:(?:\".*\")|(?:'.*'))?\s*$"),
        )

        # 针对MD项目的处理
        if ProjectType.MD in event_data.file_project_types:

            SpecialTextFilter.filter_md_text(self, event_data.items_iter(ProjectType.MD),MD_EXCLUDE_REGEXS)


    # 特殊文本过滤器——md项目
    def filter_md_text(self, cache_list: Iterator[CacheItem],MD_EXCLUDE_REGEXS):

        for entry in cache_list:
            source_text = entry.source_text

            if any(regex.match(source_text) for regex in MD_EXCLUDE_REGEXS):
                entry.translation_status = TranslationStatus.EXCLUDED
