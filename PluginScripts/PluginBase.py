from Module_Folders.Translator.TranslatorConfig import TranslatorConfig

class Priority():

    HIGHEST    = 700
    HIGHER     = 600
    HIGH       = 500
    NORMAL     = 400
    LOW        = 300
    LOWER      = 200
    LOWEST     = 100

class PluginBase:

    # 优先级列表
    PRIORITY = Priority()

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
    def on_event(self, event: str, config: TranslatorConfig, event_data: any) -> None:
        pass

    # 添加事件
    def add_event(self, event: str, priority: int) -> None:
        self.events.append(
            {
                "event": event,
                "priority": priority,
            }
        )