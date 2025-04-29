import fnmatch
from collections import Counter
from pathlib import Path
from typing import Callable

import rich

from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.BaseReader import BaseSourceReader


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
    def read_source_directory(self, source_directory: Path) -> CacheProject:
        """
        树状读取文件夹内同类型文件，检测每个文件的编码，并在最后设置项目的默认编码。

        Args:
            source_directory: 源文件目录

        Returns:
            CacheProject: 包含项目信息和文件内容
        """
        cache_project = CacheProject()  # 项目头信息
        text_index = 1  # 文本索引

        encoding_counter = Counter()  # 用于统计编码出现次数

        with self.create_reader() as reader:
            self._update_exclude_rules(reader.exclude_rules)
            cache_project.project_type = reader.get_project_type()

            for root, _, files in source_directory.walk():  # 递归遍历文件夹
                for file in files:
                    file_path = root / file
                    # 检查是否被排除，以及是否是目标类型文件
                    if not self.is_exclude(file_path, source_directory) and reader.can_read(file_path):

                        # 使用检测到的编码读取文件内容
                        # 读取单个文件的文本信息，并添加其他信息
                        cache_file = reader.read_source_file(file_path)
                        cache_file.storage_path = str(file_path.relative_to(source_directory))
                        cache_file.file_project_type = reader.get_file_project_type(file_path)
                        for item in cache_file.items:
                            item.text_index = text_index
                            item.model = 'none'
                            text_index += 1
                        if cache_file.items:
                            cache_project.add_file(cache_file)
                        encoding_counter[cache_file.encoding] += 1

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

            cache_project.detected_encoding = most_common_encoding
        else:
            rich.print("[[red]WARNING[/]] 未检测到任何文件编码信息")

        return cache_project
