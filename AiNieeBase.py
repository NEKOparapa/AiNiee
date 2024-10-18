import os
import json

from rich import print

class AiNieeBase():

    # 默认配置
    DEFAULT = {}

    # 配置文件路径
    CONFIG_PATH = "./Resource/config.json"

    def __init__(self):
        super().__init__()

        # 载入并保存默认配置
        self.save_config(self.load_config_from_default())

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
    def fill_config(self, old: dict, new: dict) -> dict:
        for k, v in new.items():
            if k not in old.keys():
                old[k] = v
            elif type(old[k]) == dict and type(v) == dict:
                self.fill_config(old[k], v)

        return old

    # 用默认值更新并加载配置文件
    def load_config_from_default(self) -> None:
        config = self.load_config()

        if len(self.DEFAULT) > 0:
            self.fill_config(config, self.DEFAULT)
                
        return config