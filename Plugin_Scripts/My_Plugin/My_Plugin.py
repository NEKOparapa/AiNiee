from ..Plugin_Base.Plugin_Base import PluginBase


class MyPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "My Plugin"
        self.description = "This is an example plugin."

    def load(self):
        print(f"{self.name} loaded!")
        print(f"My Plugin")

    def unload(self):
        print(f"{self.name} unloaded!")

    def on_event(self, event_name, data):
        if event_name == "user_login":
            print(f"{self.name} detected a login event.")
