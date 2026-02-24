import os
import json
import threading
import traceback
from rich import print
from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition

class Base:
    # 配置文件路径 (默认在上级目录的 Resource 中，也可以在当前目录)
    # 我们会在 main.py 中根据实际情况调整这个路径，或者在这里动态查找
    CONFIG_PATH = os.path.join("..", "Resource", "config.json")
    CONFIG_FILE_LOCK = threading.Lock()
    
    # 多语言支持
    multilingual_interface_dict = {}
    current_interface_language = "简中"

    @classmethod
    def tra(cls, text):
        translation = cls.multilingual_interface_dict.get(text)
        if translation:
            translation_text = translation.get(cls.current_interface_language)
            if translation_text:
                return translation_text
        return text

    def __init__(self, *args, **kwargs):
        pass

    def get_parent_window(self):
        """统一获取父窗口对象"""
        if hasattr(self, 'window'):
            if callable(self.window):
                return self.window()
            else:
                return self.window
        return None

    # Toast 消息
    def info_toast(self, title: str, content: str) -> None:
        InfoBar.info(
            title=title,
            content=content,
            parent=self.get_parent_window(),
            duration=2500,
            orient=Qt.Horizontal,
            position=InfoBarPosition.TOP,
            isClosable=True,
        )

    def error_toast(self, title: str, content: str) -> None:
        InfoBar.error(
            title=title,
            content=content,
            parent=self.get_parent_window(),
            duration=2500,
            orient=Qt.Horizontal,
            position=InfoBarPosition.TOP,
            isClosable=True,
        )

    def success_toast(self, title: str, content: str) -> None:
        InfoBar.success(
            title=title,
            content=content,
            parent=self.get_parent_window(),
            duration=2500,
            orient=Qt.Horizontal,
            position=InfoBarPosition.TOP,
            isClosable=True,
        )

    def warning_toast(self, title: str, content: str) -> None:
        InfoBar.warning(
            title=title,
            content=content,
            parent=self.get_parent_window(),
            duration=2500,
            orient=Qt.Horizontal,
            position=InfoBarPosition.TOP,
            isClosable=True,
        )

    # 配置文件操作
    def load_config(self) -> dict:
        config = {}
        with Base.CONFIG_FILE_LOCK:
            path = Base.CONFIG_PATH
            # 优先尝试当前目录
            local_path = os.path.join(".", "Resource", "config.json")
            if os.path.exists(local_path):
                path = local_path
            elif not os.path.exists(path):
                 # 如果默认路径也不存在，保持原路径尝试读取（可能会失败）
                 pass
            
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as reader:
                        config = json.load(reader)
                except Exception as e:
                    self.error(f"读取配置文件失败: {e}")
        return config

    def save_config(self, new: dict) -> None:
        old = {}
        path = Base.CONFIG_PATH
        # 确定路径
        local_path = os.path.join(".", "Resource", "config.json")
        local_dir = os.path.join(".", "Resource")
        
        # 优先使用本地配置
        if os.path.exists(local_path):
            path = local_path
        # 如果本地没有配置文件，但有资源目录，则新建在本地
        elif os.path.exists(local_dir):
            path = local_path
        # 如果默认路径不存在，且没有本地资源目录，则尝试默认路径（可能会失败）
        
        with Base.CONFIG_FILE_LOCK:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as reader:
                        old = json.load(reader)
                except:
                    pass

        # 简单合并
        for k, v in new.items():
            old[k] = v

        with Base.CONFIG_FILE_LOCK:
            try:
                with open(path, "w", encoding="utf-8") as writer:
                    writer.write(json.dumps(old, indent=4, ensure_ascii=False))
            except Exception as e:
                self.error(f"保存配置文件失败: {e}")

    # 日志方法
    def info(self, msg: str) -> None:
        print(f"[[green]INFO[/]] {msg}")

    def error(self, msg: str, e: Exception = None) -> None:
        if e is None:
            print(f"[[red]ERROR[/]] {msg}")
        else:
            print(f"[[red]ERROR[/]] {msg}\n{e}\n{(''.join(traceback.format_exception(None, e, e.__traceback__))).strip()}")

    def warning(self, msg: str) -> None:
        print(f"[[yellow]WARNING[/]] {msg}")
