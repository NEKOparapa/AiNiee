import fnmatch
import pathlib
from collections import Counter
from pathlib import Path
from typing import Callable, Union

import chardet
import rich
from magika.types import OverwriteReason

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.BaseReader import BaseSourceReader

# 全局单例
_MAGIKA_INSTANCE = None


def get_magika():
    global _MAGIKA_INSTANCE
    if _MAGIKA_INSTANCE is None:
        from magika import Magika
        _MAGIKA_INSTANCE = Magika()
    return _MAGIKA_INSTANCE


def detect_file_encoding(file_path: Union[str, pathlib.Path], min_confidence: float = 0.75) -> str:
    """
    使用Magika检测文件类型，如果是非纯文本则返回'non_text/{label}'，
    如果是纯文本则使用chardet检测编码。

    Args:
        file_path: 要检测的文件路径
        min_confidence: chardet检测编码的最低置信度阈值，低于此值将返回默认编码'utf-8'

    Returns:
        str: 对于非文本文件返回'non_text/{label}'，对于文本文件返回检测到的编码
    """
    # 确保file_path是Path对象
    if isinstance(file_path, str):
        file_path = pathlib.Path(file_path)

    # 使用Magika检测文件类型
    result = get_magika().identify_path(file_path)
    non_text = not result.output.is_text
    is_low_confidence = result.prediction.overwrite_reason == OverwriteReason.LOW_CONFIDENCE

    # 如果文件为非文本类型且没有触发`is_low_confidence`条件。则返回non_text/xxx
    # 否则继续使用chardet检查编码
    if non_text and not is_low_confidence:
        # 非文本文件，返回non_text前缀加上检测到的标签
        return f"non_text/{result.output.label}"

    # 读取文件内容
    with open(file_path, 'rb') as f:
        content_bytes = f.read()

    # 文件是文本类型，使用chardet检测编码
    detection_result = chardet.detect(content_bytes)
    detected_encoding = detection_result['encoding']
    confidence = detection_result['confidence']

    # 如果没有检测到编码或置信度低于阈值，返回默认编码'utf-8'
    if not detected_encoding or confidence < min_confidence:
        return 'utf-8'

    return detected_encoding


class DirectoryReader:
    def __init__(self, create_reader: Callable[[], BaseSourceReader], exclude_rules: list[str]):
        self.create_reader = create_reader  # 工厂函数

        self.exclude_files = set()
        self.exclude_paths = set()
        self._update_exclude_rules(exclude_rules)

    def _update_exclude_rules(self, exclude_rules):
        self.exclude_files.update({rule for rule in exclude_rules if "/" not in rule})
        self.exclude_paths.update({rule for rule in exclude_rules if "/" in rule})

    def is_exclude(self, file_path: Path, source_directory: Path):
        if any(fnmatch.fnmatch(file_path.name, rule) for rule in self.exclude_files):
            return True

        rel_path_str = str(file_path.relative_to(source_directory))
        if any(fnmatch.fnmatch(rel_path_str, pattern) for pattern in self.exclude_paths):
            return True
        return False

    # 树状读取文件夹内同类型文件
    def read_source_directory(self, source_directory: Path) -> tuple[CacheProject, list[CacheItem]]:
        """
        树状读取文件夹内同类型文件，检测每个文件的编码，并在最后设置项目的默认编码。

        Args:
            source_directory: 源文件目录

        Returns:
            tuple: 包含 (cache_project, items) 的元组
                - cache_project: 项目头信息
                - items: 文本项列表
        """
        cache_project = CacheProject({})  # 项目头信息
        text_index = 1  # 文本索引
        items = []  # 文本对信息
        encoding_counter = Counter()  # 用于统计编码出现次数

        file_project_types = set()
        with self.create_reader() as reader:
            self._update_exclude_rules(reader.exclude_rules)
            cache_project.set_project_type(reader.get_project_type())

            for root, _, files in source_directory.walk():  # 递归遍历文件夹
                for file in files:
                    file_path = root / file
                    # 检查是否被排除，以及是否是目标类型文件
                    if not self.is_exclude(file_path, source_directory) and reader.can_read(file_path):
                        # 猜测的文件编码
                        detected_encoding = detect_file_encoding(file_path)

                        # 统计编码出现次数
                        if not detected_encoding.startswith('non_text'):
                            encoding_counter[detected_encoding] += 1

                        # 确定要使用的编码
                        # 如果 `detect_file_encoding` 返回的是 `non_text` 开头（非纯文本）
                        # 则默认将传给 `read_source_file` 的编码设置为 `utf-8`
                        encoding_to_use = "utf-8" if detected_encoding.startswith("non_text") else detected_encoding

                        # 使用检测到的编码读取文件内容
                        # 读取单个文件的文本信息，并添加其他信息
                        for item in reader.read_source_file(file_path, encoding_to_use):
                            item.set_text_index(text_index)
                            item.set_model('none')
                            item.set_storage_path(str(file_path.relative_to(source_directory)))
                            item.set_file_name(file_path.name)
                            item.set_file_project_type(reader.get_file_project_type(file_path))
                            items.append(item)
                            text_index += 1
                            file_project_types.add(reader.get_file_project_type(file_path))

        # 设置目录下包含的文件项目类型，用于快速判断
        cache_project.set_file_project_types(list(file_project_types))

        # 设置项目的默认编码为最常见的编码
        if encoding_counter:
            # 获取所有编码及其文件数量，从多到少排序
            all_encodings = encoding_counter.most_common()
            total_files = sum(encoding_counter.values())

            # 打印编码统计信息
            rich.print("\n[[green]INFO[/]] 编码统计情况:")
            print("-" * 40)
            print(f"{'编码':<15} | {'文件数量':<10} | {'比例':<10}")
            print("-" * 40)

            for encoding, count in all_encodings:
                percentage = (count / total_files) * 100
                print(f"{encoding:<15} | {count:<10} | {percentage:.2f}%")

            # 设置最常见的编码为项目默认编码
            most_common_encoding = all_encodings[0][0]
            print("-" * 40)
            rich.print(
                f"[[green]INFO[/]] 项目默认编码设置为: {most_common_encoding} (共 {all_encodings[0][1]} 个文件, "
                f"占比 {(all_encodings[0][1] / total_files) * 100:.2f}%)"
            )

            cache_project.set_file_encoding(most_common_encoding)
        else:
            rich.print("[[red]WARNING[/]] 未检测到任何文件编码信息")

        return cache_project, items
