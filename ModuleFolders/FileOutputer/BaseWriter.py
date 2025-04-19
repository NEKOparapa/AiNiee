import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypedDict

from ModuleFolders.Cache.CacheItem import CacheItem


@dataclass
class TranslationOutputConfig:
    enabled: bool = False
    name_suffix: str = ""
    output_root: Path = None
    file_encoding: str = ""
    line_ending: str = ""


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


class WriterInitParams(TypedDict):
    """writer的初始化参数，必须包含output_config，其他参数随意"""
    output_config: OutputConfig


class BaseTranslationWriter(ABC):
    """Writer基类，在其生命周期内可以输出多个文件"""
    def __init__(self, output_config: OutputConfig) -> None:
        self.output_config = output_config

        # 提取译文输出的编码和换行符配置
        self.translated_encoding = output_config.translated_config.file_encoding or "utf-8"
        self.translated_line_ending = output_config.translated_config.line_ending or os.linesep

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
