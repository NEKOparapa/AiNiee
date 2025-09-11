from pathlib import Path
from typing import Callable

import rich

from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileOutputer import WriterUtil
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    BaseTranslationWriter,
    TranslationOutputConfig
)


class DirectoryWriter:
    def __init__(self, create_writer: Callable[[], BaseTranslationWriter]):
        self.create_writer = create_writer

    WRITER_TYPE_CONFIG = {
        BaseTranslatedWriter: ("translated_config", "write_translated_file"),
        BaseBilingualWriter: ("bilingual_config", "write_bilingual_file"),
    }

    def write_translation_directory(
        self, project: CacheProject, source_directory: Path,
        translation_directory: Path = None,
    ):
        """translation_directory 用于覆盖配置"""
        with self.create_writer() as writer:
            # 判断输入路径是目录还是文件
            is_source_a_directory = source_directory.is_dir()
            
            # 把翻译片段按文件名分组
            for storage_path, file_items in project.files.items():
                # 根据输入路径的类型决定如何构造源文件路径
                if is_source_a_directory:
                    # 如果是目录，则拼接相对路径
                    source_file_path = source_directory / storage_path
                else:
                    # 如果是文件，则输入路径本身就是源文件路径
                    source_file_path = source_directory
                for translation_mode in BaseTranslationWriter.TranslationMode:
                    if writer.can_write(translation_mode):
                        translation_config: TranslationOutputConfig = getattr(
                            writer.output_config, translation_mode.config_attr
                        )
                        # 替换文件后缀
                        new_storage_path = self.with_file_suffix(storage_path, translation_config.name_suffix)
                        output_root = translation_directory or translation_config.output_root
                        translation_file_path = output_root / new_storage_path
                        if not translation_file_path.parent.exists():
                            translation_file_path.parent.mkdir(parents=True, exist_ok=True)
                        write_translation_file = getattr(writer, translation_mode.write_method)

                        # 执行写入
                        write_translation_file(translation_file_path, file_items, source_file_path)
        # 释放Ainiee配置实例
        WriterUtil.release_ainiee_config()

    @classmethod
    def with_file_suffix(self, file_path: str, name_suffix: str) -> Path:
        parts = file_path.rsplit(".", 1)
        if len(parts) == 2:
            return f"{parts[0]}{name_suffix}.{parts[1]}"
        else:
            return f"{parts[0]}{name_suffix}"
