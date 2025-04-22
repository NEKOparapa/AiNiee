from collections import defaultdict
from pathlib import Path
from typing import Callable

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


def group_to_list[E, R](arr: list[E], key: Callable[[E], R]):
    result = defaultdict[R, list[E]](list)
    for x in arr:
        result[key(x)].append(x)
    return result


class DirectoryWriter:
    def __init__(self, create_writer: Callable[[], BaseTranslationWriter]):
        self.create_writer = create_writer

    WRITER_TYPE_CONFIG = {
        BaseTranslatedWriter: ("translated_config", "write_translated_file"),
        BaseBilingualWriter: ("bilingual_config", "write_bilingual_file"),
    }

    def write_translation_directory(
        self, items: list[CacheItem], source_directory: Path,
        translation_directory: Path = None,
    ):
        """translation_directory 用于覆盖配置"""
        with self.create_writer() as writer:
            # 获取项目的文件属性
            proj_file_props = writer.proj_file_props
            # 把翻译片段按文件名分组
            items_dict = group_to_list(items, lambda x: x.get_storage_path())

            for storage_path, file_items in items_dict.items():
                # 获取文件的原始编码
                if storage_path in proj_file_props and "original_encoding" in proj_file_props[storage_path]:
                    original_encoding = proj_file_props[storage_path]["original_encoding"]
                else:
                    # 默认使用UTF-8
                    original_encoding = "utf-8"

                use_original_encoding = True

                # 检查该文件的所有文本是否可以用原始编码表示
                # 如果原始编码已经是UTF-8，跳过检查
                # 如果原始编码为非纯文本，跳过检查
                if original_encoding.lower() == 'utf-8' or original_encoding.startswith("non_text"):
                    pass  # UTF-8可以表示所有字符，无需检查 / 非纯文本不需要检查
                else:
                    # 检查所有文本是否可以用原始编码表示
                    for item in file_items:
                        if item.translated_text and not can_encode_text(item.translated_text, original_encoding):
                            use_original_encoding = False
                            break

                # 决定使用的编码
                actual_encoding = original_encoding if use_original_encoding else 'utf-8'

                source_file_path = source_directory / storage_path
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
                        # 判断是否为直接写出（原始）的翻译文件
                        is_direct_trans_file = translation_mode == BaseTranslationWriter.TranslationMode.TRANSLATED
                        # 为每个文件单独决定编码，同时仅将原始的译文设置为对应编码
                        writer.checked_file_encodings[translation_file_path] = actual_encoding if is_direct_trans_file else "utf-8"
                        if is_direct_trans_file:
                            rich.print(
                                f"[[green]INFO[/]] 正在写入文件 {storage_path}, 使用编码: {actual_encoding} "
                                f"{'(原始编码)' if use_original_encoding else f'(由原始编码 {original_encoding} 变更)'}"
                            )
                        write_translation_file(translation_file_path, file_items, source_file_path)

            # 文件写入完成后清除字典属性
            writer.checked_file_encodings.clear()

    @classmethod
    def with_file_suffix(self, file_path: str, name_suffix: str) -> Path:
        parts = file_path.rsplit(".", 1)
        if len(parts) == 2:
            return f"{parts[0]}{name_suffix}.{parts[1]}"
        else:
            return f"{parts[0]}{name_suffix}"
