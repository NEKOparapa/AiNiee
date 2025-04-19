import re
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


    def on_event(self, event_name, config, event_data):

        # 文本预处理事件触发
        if event_name == "text_filter":

            items = event_data[1:]
            project = event_data[0]

            # 正对trans项目的处理
            if "Trans" in project.get("file_project_types", ()):

                SpecialTextFilter.filter_trans_text(self, (item for item in items if item.get("file_project_type") == 'Trans'))


            # 针对MD项目的处理
            if "Md" in project.get("file_project_types", ()):

                SpecialTextFilter.filter_md_text(self, (item for item in items if item.get("file_project_type") == 'Md'))

    # 特殊文本过滤器
    def filter_trans_text(self,cache_list):
        for entry in cache_list:
            tags = entry.get('tags',"")
            if tags and ("red" in tags):
                entry['translation_status'] =  7



    # 特殊文本过滤器
    def filter_md_text(self,cache_list):

        # 1.  ![...](http://...) and ![...](data:image...)
        REGEX_INLINE_IMAGE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")

        # 2.  ![alt][id]
        REGEX_REF_IMAGE_USAGE = re.compile(r"^\s*!\[[^\]]*\]\[[^\]]+\]\s*$")

        # 3.  [id]: url "title" or [id]: <url> "title"
        REGEX_REF_DEFINITION = re.compile(r"^\s*\[[^\]]+\]:\s*<?.*>?\s*(?:(?:\".*\")|(?:'.*'))?\s*$")

        for entry in cache_list:
            source_text = entry.get('source_text')

            if REGEX_INLINE_IMAGE.match(source_text) or \
               REGEX_REF_IMAGE_USAGE.match(source_text) or \
               REGEX_REF_DEFINITION.match(source_text):
                entry['translation_status'] = 7