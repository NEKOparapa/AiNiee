from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem


@dataclass
class InputConfig:
    input_root: Path


class BaseSourceReader(ABC):
    def __init__(self, input_config: InputConfig) -> None:
        self.input_config = input_config

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        pass

    @classmethod
    @abstractmethod
    def get_project_type(cls) -> str:
        pass

    @property
    @abstractmethod
    def support_file(self) -> str:
        pass

    @abstractmethod
    def read_source_file(self, file_path: Path) -> list[CacheItem]:
        pass

    def can_read(self, file_path: Path) -> bool:
        if file_path.suffix.replace('.', '', 1) != self.support_file:
            return False
        return True


def text_to_cache_item(source_text, translated_text: str = None):
    item = CacheItem({})
    item.set_source_text(source_text)
    if translated_text is None:
        translated_text = source_text
    item.set_translated_text(translated_text)
    item.set_translation_status(CacheItem.STATUS.UNTRANSLATED)
    return item
