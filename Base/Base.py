import os
import threading
import traceback

import rapidjson as json
from rich import print
from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBar
from qfluentwidgets import InfoBarPosition

from Base.EventManager import EventManager

class Event():

    API_TEST_DONE = 100                             # API 测试完成
    API_TEST_START = 101                            # API 测试开始
    TRANSLATION_START = 210                         # 翻译开始
    TRANSLATION_UPDATE = 220                        # 翻译状态更新
    TRANSLATION_STOP = 230                          # 翻译停止
    TRANSLATION_STOP_DONE = 231                     # 翻译停止完成
    TRANSLATION_CONTINUE_CHECK = 240                # 继续翻译状态检查
    TRANSLATION_CONTINUE_CHECK_DONE = 241           # 继续翻译状态检查完成
    TRANSLATION_MANUAL_EXPORT = 250                 # 翻译结果手动导出
    CACHE_FILE_AUTO_SAVE = 300                      # 缓存文件自动保存
    APP_SHUT_DOWN = 1000                            # 应用关闭


class Status():

    IDLE = 1000                                     # 无任务
    API_TEST = 2000                                 # 测试中
    TRANSLATING = 3000                              # 翻译中
    STOPING = 4000                                  # 停止中

class Base():

    # 事件列表
    EVENT = Event()

    # 状态列表
    STATUS = Status()

    # 配置文件路径
    CONFIG_PATH = "./Resource/config.json"

    # 类线程锁
    CONFIG_FILE_LOCK = threading.Lock()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # 默认配置
        self.default = {}

        # 获取事件管理器单例
        self.event_manager_singleton = EventManager()

        # 类变量
        Base.work_status = Base.STATUS.IDLE if not hasattr(Base, "work_status") else Base.work_status

    # PRINT
    def print(self, msg: str) -> None:
        print(msg)

    # DEBUG
    def debug(self, msg: str, e: Exception = None) -> None:
        if self.is_debug() == True:
            if e == None:
                print(f"[[yellow]DEBUG[/]] {msg}")
            else:
                print(f"[[yellow]DEBUG[/]] {msg}\n{e}\n{("".join(traceback.format_exception(None, e, e.__traceback__))).strip()}")

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
    def info_toast(self, title: str, content: str) -> None:
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
    def error_toast(self, title: str, content: str) -> None:
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
    def success_toast(self, title: str, content: str) -> None:
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
    def warning_toast(self, title: str, content: str) -> None:
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

        with Base.CONFIG_FILE_LOCK:
            if os.path.exists(Base.CONFIG_PATH):
                with open(Base.CONFIG_PATH, "r", encoding = "utf-8") as reader:
                    config = json.load(reader)
            else:
                self.warning("配置文件不存在 ...")

        return config

    # 保存配置文件
    def save_config(self, new: dict) -> None:
        old = {}

        # 读取配置文件
        with Base.CONFIG_FILE_LOCK:
            if os.path.exists(Base.CONFIG_PATH):
                with open(Base.CONFIG_PATH, "r", encoding = "utf-8") as reader:
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
        with Base.CONFIG_FILE_LOCK:
            with open(Base.CONFIG_PATH, "w", encoding = "utf-8") as writer:
                writer.write(json.dumps(old, indent = 4, ensure_ascii = False))

        return old

    # 更新配置
    def fill_config(self, old: dict, new: dict) -> dict:
        for k, v in new.items():
            if k not in old.keys():
                old[k] = v

        return old

    # 用默认值更新并加载配置文件
    def load_config_from_default(self) -> None:
        config = self.load_config()
        config = self.fill_config(config, getattr(self, "default", {}))

        return config

    # 触发事件
    def emit(self, event: int, data: dict) -> None:
        EventManager.get_singleton().emit(event, data)

    # 订阅事件
    def subscribe(self, event: int, hanlder: callable) -> None:
        EventManager.get_singleton().subscribe(event, hanlder)

    # 取消订阅事件
    def unsubscribe(self, event: int, hanlder: callable) -> None:
        EventManager.get_singleton().unsubscribe(event, hanlder)

    # 检查是否为开发模式
    def is_debug(self) -> bool:
        if not hasattr(Base, "_is_debug"):
            Base._is_debug = os.path.isfile("./debug.txt")

        return Base._is_debug