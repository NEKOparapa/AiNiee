import os
import traceback

import rapidjson as json
from rich import print
from PyQt5.Qt import Qt
from qfluentwidgets import InfoBar
from qfluentwidgets import InfoBarPosition

from Base.EventManager import EventManager

class Base():

    # 事件列表
    EVENT = type("GClass", (), {})()
    EVENT.API_TEST_DONE = 100                       # API 测试完成
    EVENT.API_TEST_START = 101                      # API 测试开始
    EVENT.TRANSLATION_START = 210                   # 翻译开始
    EVENT.TRANSLATION_UPDATE = 220                  # 翻译状态更新
    EVENT.TRANSLATION_STOP = 230                    # 翻译停止
    EVENT.TRANSLATION_STOP_DONE = 231               # 翻译停止完成
    EVENT.TRANSLATION_CONTINUE_CHECK = 240          # 继续翻译状态检查
    EVENT.TRANSLATION_CONTINUE_CHECK_DONE = 241     # 继续翻译状态检查完成
    EVENT.TRANSLATION_MANUAL_EXPORT = 250           # 翻译结果手动导出
    EVENT.CACHE_FILE_AUTO_SAVE = 300                # 缓存文件自动保存
    EVENT.APP_SHUT_DOWN = 1000                      # 应用关闭

    # 状态列表
    STATUS = type("GClass", (), {})()
    STATUS.IDLE = 100             # 无任务
    STATUS.API_TEST = 110         # 测试中
    STATUS.TRANSLATION = 120      # 翻译中
    STATUS.STOPING = 130          # 停止中

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

        # 获取事件管理器单例
        self.event_manager_singleton = EventManager()

        # 载入并保存默认配置
        if len(self.DEFAULT) > 0:
            self.save_config(self.load_config_from_default(self.DEFAULT_FILL.SELECT_MODE))

    # PRINT
    def print(self, msg: str) -> None:
        print(msg)

    # INFO
    def info(self, msg: str) -> None:
        print(f"[[green]INFO[/]] {msg}")

    # ERROR
    def error(self, msg: str, e: Exception = None) -> None:
        if e == None:
            print(f"[[red]ERROR[/]] {msg}")
        else:
            print(f"[[red]ERROR[/]] {msg}\n{e}\n{("".join(traceback.format_exception(None, e, e.__traceback__))).strip()}")

    # WARNING
    def warning(self, msg: str) -> None:
        print(f"[[red]WARNING[/]] {msg}")

    # Toast
    def info_toast(self, title, content) -> None:
        InfoBar.info(
            title = title,
            content = content,
            parent = self,
            duration = 2500,
            orient = Qt.Horizontal,
            position = InfoBarPosition.TOP,
            isClosable = True,
        )

    # Toast
    def error_toast(self, title, content) -> None:
        InfoBar.error(
            title = title,
            content = content,
            parent = self,
            duration = 2500,
            orient = Qt.Horizontal,
            position = InfoBarPosition.TOP,
            isClosable = True,
        )

    # Toast
    def success_toast(self, title, content) -> None:
        InfoBar.success(
            title = title,
            content = content,
            parent = self,
            duration = 2500,
            orient = Qt.Horizontal,
            position = InfoBarPosition.TOP,
            isClosable = True,
        )

    # Toast
    def warning_toast(self, title, content) -> None:
        InfoBar.warning(
            title = title,
            content = content,
            parent = self,
            duration = 2500,
            orient = Qt.Horizontal,
            position = InfoBarPosition.TOP,
            isClosable = True,
        )

    # 载入配置文件
    def load_config(self) -> dict:
        config = {}

        if os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, "r", encoding = "utf-8") as reader:
                config = json.load(reader)
        else:
            self.warning("配置文件不存在 ...")

        return config

    # 保存配置文件
    def save_config(self, new: dict) -> None:
        old = {}

        # 读取配置文件
        if os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, "r", encoding = "utf-8") as reader:
                old = json.load(reader)

        # 对比新旧数据是否一致，一致则跳过后续步骤
        # 当字典中包含子字典或子列表时，使用 == 运算符仍然可以进行比较
        # Python 会递归地比较所有嵌套的结构，确保每个层次的键值对都相等
        if old == new:
            return old

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

    # 触发事件
    def emit(self, event: int, data: dict):
        EventManager.get_singleton().emit(event, data)

    # 订阅事件
    def subscribe(self, event: int, hanlder: callable):
        EventManager.get_singleton().subscribe(event, hanlder)

    # 取消订阅事件
    def unsubscribe(self, event: int, hanlder: callable):
        EventManager.get_singleton().unsubscribe(event, hanlder)

    # 检查是否为开发模式
    def is_debug(self):
        if not hasattr(Base, "_is_debug"):
            Base._is_debug = os.path.exists("./debug.txt")

        return Base._is_debug