import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TypedDict

import rich

from ModuleFolders.Cache.CacheItem import CacheItem


@dataclass
class TranslationOutputConfig:
    enabled: bool = False
    name_suffix: str = ""
    output_root: Path = None
    file_props: dict = None


@dataclass
class OutputConfig:
    translated_config: TranslationOutputConfig = None
    bilingual_config: TranslationOutputConfig = None
    input_root: Path = None

    def __post_init__(self):
        if self.translated_config is None:
            self.translated_config = TranslationOutputConfig(True, "_translated")
        if self.bilingual_config is None:
            self.bilingual_config = TranslationOutputConfig(False, "_bilingual")


class NewFileEncDict:
    def __init__(self):
        self._dict = {}
        self._lock = threading.Lock()

    def __getitem__(self, key):
        with self._lock:
            return self._dict[key]

    def __setitem__(self, key, value):
        with self._lock:
            self._dict[key] = value

    def get(self, key, default=None):
        with self._lock:
            return self._dict.get(key, default)

    def clear(self):
        """清空字典中的所有项"""
        with self._lock:
            rich.print(f"[[green]INFO[/]] 文件写入完成, 共{len(self._dict)}个文件")
            self._dict.clear()

    def __str__(self):
        """当使用print()打印字典时调用"""
        with self._lock:
            return str(self._dict)

    def __repr__(self):
        """在交互式环境中显示字典内容时调用"""
        with self._lock:
            return repr(self._dict)

    def __contains__(self, key):
        """支持 'key in dict' 操作"""
        with self._lock:
            return key in self._dict

    def __len__(self):
        """支持 len(dict) 操作"""
        with self._lock:
            return len(self._dict)


# 创建一个全局实例
global_new_file_enc_dict = NewFileEncDict()


class WriterInitParams(TypedDict):
    """writer的初始化参数，必须包含output_config，其他参数随意"""
    output_config: OutputConfig


class BaseTranslationWriter(ABC):
    """Writer基类，在其生命周期内可以输出多个文件"""
    def __init__(self, output_config: OutputConfig) -> None:
        self.output_config = output_config

        # 提取项目的（多个）文件属性（编码，语言等）
        self.proj_file_props = output_config.translated_config.file_props
        # 检查兼容性后的文件属性（仅包含每个文件的编码）
        self.checked_file_encodings = global_new_file_enc_dict

    class TranslationMode(Enum):
        TRANSLATED = ('translated_config', 'write_translated_file')
        BILINGUAL = ('bilingual_config', 'write_bilingual_file')

        def __init__(self, config_attr, write_method) -> None:
            self.config_attr = config_attr
            self.write_method = write_method

    def can_write(self, mode: TranslationMode) -> bool:
        """判断writer是否支持该输出方式"""
        if mode == self.TranslationMode.TRANSLATED:
            return isinstance(self, BaseTranslatedWriter) and self.output_config.translated_config.enabled
        elif mode == self.TranslationMode.BILINGUAL:
            return isinstance(self, BaseBilingualWriter) and self.output_config.bilingual_config.enabled
        return False

    NOT_TRANSLATED_STATUS = (CacheItem.STATUS.UNTRANSLATED, CacheItem.STATUS.TRANSLATING)

    def __enter__(self):
        """申请整个Writer生命周期用到的耗时资源，单个文件的资源则在write_xxx_file方法中申请释放"""
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        """释放耗时资源"""
        pass

    @classmethod
    @abstractmethod
    def get_project_type(self) -> str:
        """获取Writer对应的项目类型标识符（用于动态实例化），如 Mtool"""
        pass

    @classmethod
    def is_environ_supported(cls) -> bool:
        """用于判断当前环境是否支持该writer"""
        return True


class BaseTranslatedWriter(BaseTranslationWriter):
    """译文输出基类"""

    @abstractmethod
    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        """输出译文文件"""
        pass


class BaseBilingualWriter(BaseTranslationWriter):
    """双语输出基类"""

    @abstractmethod
    def write_bilingual_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        """输出双语文件"""
        pass
