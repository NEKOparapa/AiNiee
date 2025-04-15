import os
from itertools import groupby
from pathlib import Path
from typing import Callable, Type

import rich

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    BaseTranslationWriter,
    TranslationOutputConfig
)


def can_encode_text(text: str, encoding: str) -> bool:
    """检查文本是否可以用指定编码正确表示"""
    if not text:
        return True
    try:
        text.encode(encoding, errors='strict')
        return True
    except UnicodeEncodeError:
        return False


class DirectoryWriter:
    def __init__(self, create_writer: Callable[[], BaseTranslationWriter]):
        self.create_writer = create_writer

    WRITER_TYPE_CONFIG = {
        BaseTranslatedWriter: ("translated_config", "write_translated_file"),
        BaseBilingualWriter: ("bilingual_config", "write_bilingual_file"),
    }

    def _get_write_config(self, writer: BaseTranslationWriter, writer_type: Type):
        if not isinstance(writer, writer_type):
            return None
        translation_config: TranslationOutputConfig = getattr(
            writer.output_config,
            self.WRITER_TYPE_CONFIG[writer_type][0],
            None
        )
        return translation_config

    def write_translation_directory(
        self, items: list[CacheItem], source_directory: Path,
        translation_directory: Path = None,
    ):
        """translation_directory 用于覆盖配置"""
        with self.create_writer() as writer:
            # 首先检查所有文本是否可以用原始编码表示
            original_encoding = writer.translated_encoding
            use_original_encoding = True

            # 检查所有文本是否可以用原始编码表示
            for item in items:
                if item.translated_text and not can_encode_text(item.translated_text, original_encoding):
                    use_original_encoding = False
                    break

            # 决定使用的编码
            actual_encoding = original_encoding if use_original_encoding else 'utf-8'
            # 临时修改writer的编码设置
            writer.translated_encoding = actual_encoding

            rich.print(
                f"[[green]INFO[/]] 正在写入文件 使用编码: {actual_encoding} "
                f"{'(原始编码)' if use_original_encoding else f'(由{original_encoding}编码回退)'}"
            )

            # 把翻译片段按文件名分组
            items_dict = {k: list(v) for k, v in groupby(items, key=lambda x: x.get_storage_path())}
            for storage_path, file_items in items_dict.items():
                source_file_path = source_directory / storage_path
                for cls, (_, write_method) in self.WRITER_TYPE_CONFIG.items():
                    translation_config = self._get_write_config(writer, cls)
                    if translation_config and translation_config.enabled:
                        # 替换文件后缀
                        new_storage_path = self.with_file_suffix(storage_path, translation_config.name_suffix)
                        output_root = translation_directory or translation_config.output_root
                        translation_file_path = output_root / new_storage_path
                        if not translation_file_path.parent.exists():
                            translation_file_path.parent.mkdir(parents=True, exist_ok=True)
                        write_translation_file = getattr(writer, write_method)

                        # 执行写入
                        write_translation_file(translation_file_path, file_items, source_file_path)

    @classmethod
    def with_file_suffix(self, file_path: str, name_suffix: str) -> Path:
        parts = file_path.rsplit(".", 1)
        if len(parts) == 2:
            return f"{parts[0]}{name_suffix}.{parts[1]}"
        else:
            return f"{parts[0]}{name_suffix}"
