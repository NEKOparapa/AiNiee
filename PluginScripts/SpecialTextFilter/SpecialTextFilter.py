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
            if "trans"  in project.get("project_type", "").lower():

                SpecialTextFilter.filter_trans_text(self, items)


    # 特殊文本过滤器
    def filter_trans_text(self,cache_list):
        for entry in cache_list:
            tags = entry.get('tags',"")
            if "red" in tags:
                entry['translation_status'] = 7

