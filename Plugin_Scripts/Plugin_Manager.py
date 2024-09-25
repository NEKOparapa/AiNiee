import importlib
import os
from pathlib import Path
from .Plugin_Base.Plugin_Base import PluginBase

class Plugin_Manager:
    def __init__(self):
        self.plugins = []

    def load_plugin(self, plugin_class):
        plugin_instance = plugin_class()
        plugin_instance.load()
        self.plugins.append(plugin_instance)

    def unload_plugin(self, plugin_instance):
        plugin_instance.unload()
        self.plugins.remove(plugin_instance)

    def broadcast_event(self, event_name, configuration_information = None, event_data = None):
        for plugin in self.plugins:
            plugin.on_event(event_name, configuration_information, event_data)


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