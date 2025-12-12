import importlib
import os
from pathlib import Path
from PluginScripts.PluginBase import PluginBase

class PluginManager:

    def __init__(self):

        # 使用字典来存储每个事件对应的插件列表
        self.event_plugins = {}

        # 记录每个插件的启用状态
        self.plugins_enable = {}

    def load_plugin(self, plugin_class):
        plugin_instance = plugin_class()
        plugin_instance.load()

        # 注册插件到所有它感兴趣的事件，但不进行排序
        for event_info in plugin_instance.events:
            event_name = event_info['event']
            if event_name not in self.event_plugins:
                self.event_plugins[event_name] = []
            self.event_plugins[event_name].append(plugin_instance)

    def unload_plugin(self, plugin_instance):
        pass

    def broadcast_event(self, event_name, config=None, event_data=None):
        # 只触发注册了该事件的插件，并在调用前进行排序
        if event_name in self.event_plugins:
            # 根据优先级进行排序
            sorted_plugins = sorted(
                self.event_plugins[event_name],
                key=lambda x: next((event['priority'] for event in x.events if event['event'] == event_name), 0),
                reverse=True
            )

            # 根据启用状态进行过滤，默认为启用
            sorted_plugins = [plugin for plugin in sorted_plugins if self.plugins_enable.get(plugin.name, True)]

            #print(sorted_plugins) #bug用
            for plugin in sorted_plugins:
                plugin.on_event(event_name, config, event_data)

    def load_plugins_from_directory(self, directory):
        directory_path = Path(directory)
        for py_file in directory_path.rglob('*.py'):  # 使用rglob递归地查找所有.py文件
            if py_file.name.startswith('__'):  # 跳过以__开头的文件
                continue
            if py_file.stem == "Plugin_Manager.py":  # 跳过Plugin_Manager.py文件
                continue

            # 构建模块名，需要将文件路径转换为模块路径
            module_path = py_file.relative_to(directory_path.parent).with_suffix('')
            module_name = str(module_path).replace(os.sep, '.')

            # 动态导入模块
            module = importlib.import_module(module_name)

            # 遍历模块属性，查找插件
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if isinstance(attribute, type) and issubclass(attribute, PluginBase) and attribute is not PluginBase:
                    self.load_plugin(attribute)

    # 生成插件列表
    def get_plugins(self) -> dict:
        plugins = {}

        for k, v in self.event_plugins.items():
            for item in v:
                if item.visibility == True:
                    plugins[item.name] = item

        return plugins

    # 更新插件启用状态
    def update_plugins_enable(self, plugins_enable):
        self.plugins_enable = plugins_enable