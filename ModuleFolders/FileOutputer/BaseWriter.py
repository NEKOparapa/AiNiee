from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem


@dataclass
class TranslationOutputConfig:
    enabled: bool = False
    name_suffix: str = ""
    output_root: Path = None


@dataclass
class OutputConfig:
    translated_config: TranslationOutputConfig = None
    bilingual_config: TranslationOutputConfig = None

    def __post_init__(self):
        if self.translated_config is None:
            self.translated_config = TranslationOutputConfig(True, "_translated")
        if self.bilingual_config is None:
            self.bilingual_config = TranslationOutputConfig(False, "_bilingual")


class BaseTranslationWriter(ABC):
    def __init__(self, output_config: OutputConfig) -> None:
        self.output_config = output_config

    NOT_TRANSLATED_STATUS = (CacheItem.STATUS.UNTRANSLATED, CacheItem.STATUS.TRANSLATING)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        pass

    @classmethod
    @abstractmethod
    def get_project_type(self) -> str:
        pass


class BaseTranslatedWriter(BaseTranslationWriter):

    @abstractmethod
    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        pass


class BaseBilingualWriter(BaseTranslationWriter):

    @abstractmethod
    def write_bilingual_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        pass
