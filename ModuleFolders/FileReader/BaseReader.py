from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem


@dataclass
class InputConfig:
    input_root: Path


class BaseSourceReader(ABC):
    """Reader基类，在其生命周期内可以输入多个文件"""
    def __init__(self, input_config: InputConfig) -> None:
        self.input_config = input_config

    def __enter__(self):
        """申请整个Reader生命周期用到的耗时资源，单个文件的资源则在read_source_file方法中申请释放"""
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        """释放耗时资源"""
        pass

    @classmethod
    @abstractmethod
    def get_project_type(cls) -> str:
        """获取Reader对应的项目类型标识符（用于动态实例化），如 Mtool"""
        pass

    @property
    @abstractmethod
    def support_file(self) -> str:
        """该读取器支持处理的文件扩展名（不带点），如 json"""
        pass

    @abstractmethod
    def read_source_file(self, file_path: Path) -> list[CacheItem]:
        """读取文件内容，并返回原文(译文)片段"""
        pass

    def can_read(self, file_path: Path) -> bool:
        """验证文件兼容性，返回False则不会读取该文件"""
        if file_path.suffix.replace('.', '', 1) != self.support_file:
            return False
        return True

# 存储文本对及翻译状态信息
def text_to_cache_item(source_text, translated_text: str = None):
    item = CacheItem({})
    item.set_source_text(source_text)
    if translated_text is None:
        translated_text = source_text
    item.set_translated_text(translated_text)
    item.set_translation_status(CacheItem.STATUS.UNTRANSLATED)
    return item
