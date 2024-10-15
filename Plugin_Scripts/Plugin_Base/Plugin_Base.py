class PluginBase:
    def __init__(self):
        self.name = "Unnamed Plugin"
        self.description = "No description provided."

        self.visibility = True # 是否在插件设置中显示
        self.default_enable = True # 默认启用状态

        self.events = []  # 插件感兴趣的事件列表，使用字典存储事件名和优先级

    def load(self):
        """加载插件时调用"""
        pass

    def on_event(self, event_name, configuration_information, event_data):
        """处理事件"""
        pass


    def add_event(self, event_name, priority):
        # 添加事件和对应的优先级到事件列表
        self.events.append({'event': event_name, 'priority': priority})