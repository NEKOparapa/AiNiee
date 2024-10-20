import os
import json

from rich import print

class AiNieeBase():

    # 默认配置
    DEFAULT = {}

    # 默认配置填充模式
    DEFAULT_FILL = type("GClass", (), {})()
    DEFAULT_FILL.MODE_NORMAL = 10                               # 普通填充，只填充配置字典的直接字段
    DEFAULT_FILL.MODE_TRAVERSAL = 20                            # 遍历填充，遍历默认配置字典中所有子字典，填充所有不存在的值
    DEFAULT_FILL.SELECT_MODE = DEFAULT_FILL.MODE_TRAVERSAL      # 默认为遍历填充

    # 配置文件路径
    CONFIG_PATH = "./Resource/config.json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 载入并保存默认配置
        self.save_config(self.load_config_from_default(self.DEFAULT_FILL.SELECT_MODE))

    # INFO
    def info(self, msg: str) -> None:
        print(f"[[green]INFO[/]] {msg}")

    # ERROR
    def error(self, msg: str) -> None:
        print(f"[[red]ERROR[/]] {msg}")

    # WARNING
    def WARNING(self, msg: str) -> None:
        print(f"[[red]WARNING[/]] {msg}")

    # 载入配置文件
    def load_config(self) -> dict:
        config = {}

        if os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, "r", encoding = "utf-8") as reader:
                config = json.load(reader)
        else:
            self.error("配置文件不存在 ...")

        return config

    # 保存配置文件
    def save_config(self, new: dict) -> None:        
        old = {}

        # 读取配置文件
        if os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, "r", encoding = "utf-8") as reader:
                old = json.load(reader)
        else:
            self.error("配置文件不存在 ...")

        # 更新配置数据
        for k, v in new.items():
            if k not in old.keys():
                old[k] = v
            else:
                old[k] = new[k]

        # 写入配置文件
        with open(self.CONFIG_PATH, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(old, indent = 4, ensure_ascii = False))

        return old

    # 更新配置
    def fill_config(self, old: dict, new: dict, mode: int) -> dict:
        for k, v in new.items():
            if k not in old.keys():
                old[k] = v
            elif mode == self.DEFAULT_FILL.MODE_TRAVERSAL and type(old[k]) == dict and type(v) == dict:
                self.fill_config(old[k], v, mode)

        return old

    # 用默认值更新并加载配置文件
    def load_config_from_default(self, mode: int) -> None:
        config = self.load_config()

        if len(self.DEFAULT) > 0:
            config = self.fill_config(config, self.DEFAULT, mode)

        return config