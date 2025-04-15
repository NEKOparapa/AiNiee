import pathlib
from collections import Counter
from pathlib import Path
from typing import Callable, Union

import chardet

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.BaseReader import BaseSourceReader


def detect_encoding_with_chardet(file_path: Union[str, pathlib.Path], min_confidence: float = 0.75) -> str:
    """
    使用chardet库检测文件的编码。
    如果检测置信度低于指定阈值，则默认返回'utf-8'。

    Args:
        file_path: 要检测编码的文件路径
        min_confidence: 最低置信度阈值，低于此值将返回默认编码'utf-8'

    Returns:
        str: 检测到的编码或默认的'utf-8'
    """
    # 确保file_path是Path对象
    if isinstance(file_path, str):
        file_path = pathlib.Path(file_path)

    # 读取文件内容
    with open(file_path, 'rb') as f:
        content_bytes = f.read()

    # 使用chardet检测编码
    detection_result = chardet.detect(content_bytes)
    detected_encoding = detection_result['encoding']
    confidence = detection_result['confidence']

    # 如果没有检测到编码或置信度低于阈值，返回默认编码'utf-8'
    if not detected_encoding or confidence < min_confidence:
        return 'utf-8'

    return detected_encoding


class DirectoryReader:
    def __init__(self, create_reader: Callable[[], BaseSourceReader]):
        self.create_reader = create_reader  # 工厂函数

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

        with self.create_reader() as reader:
            cache_project.set_project_type(reader.get_project_type())

            for root, _, files in source_directory.walk():  # 递归遍历文件夹
                for file in files:
                    file_path = root / file
                    if reader.can_read(file_path):  # 检查是否为目标类型文件
                        # 猜测的文件编码
                        detected_encoding = detect_encoding_with_chardet(file_path)

                        # 统计编码出现次数
                        encoding_counter[detected_encoding] += 1

                        # 使用检测到的编码读取文件内容
                        # 读取单个文件的文本信息，并添加其他信息
                        for item in reader.read_source_file(file_path, detected_encoding):
                            item.set_text_index(text_index)
                            item.set_model('none')
                            item.set_storage_path(str(file_path.relative_to(source_directory)))
                            item.set_file_name(file_path.name)
                            items.append(item)
                            text_index += 1

        # 设置项目的默认编码为最常见的编码
        if encoding_counter:
            most_common_encoding = encoding_counter.most_common(1)[0][0]
            cache_project.set_file_encoding(most_common_encoding)

        return cache_project, items
