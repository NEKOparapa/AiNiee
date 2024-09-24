class PluginBase:
    def __init__(self):
        self.name = "Unnamed Plugin"
        self.description = "No description provided."


    def load(self):
        """加载插件时调用"""
        pass

    def on_event(self, event_name, data):
        """处理事件"""
        pass
