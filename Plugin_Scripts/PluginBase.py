from types import SimpleNamespace

class PluginBase:

    # 优先级
    PRIORITY = SimpleNamespace()
    PRIORITY.HIGHEST    = 700
    PRIORITY.HIGHER     = 600
    PRIORITY.HIGH       = 500
    PRIORITY.NORMAL     = 400
    PRIORITY.LOW        = 300
    PRIORITY.LOWER      = 200
    PRIORITY.LOWEST     = 100

    def __init__(self) -> None:
        self.name = "Unnamed Plugin"
        self.description = "No description provided."

        self.visibility = True      # 是否在插件设置中显示
        self.default_enable = True  # 默认启用状态

        self.events = []            # 插件感兴趣的事件列表，使用字典存储事件名和优先级

    # 加载插件时调用
    def load(self) -> None:
        pass

    # 处理事件
    def on_event(self, event: str, configuration_information: dict, event_data: list) -> None:
        pass

    # 添加事件
    def add_event(self, event: str, priority: int) -> None:
        self.events.append(
            {
                "event": event,
                "priority": priority,
            }
        )