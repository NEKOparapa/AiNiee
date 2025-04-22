import fnmatch
from collections import Counter
from pathlib import Path
from typing import Callable

import rich


from ModuleFolders.Cache.CacheItem import CacheItem
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

                        # 读取单个文件的文本信息，并添加其他信息
                        for item in reader.read_source_file(file_path, "utf-8"):
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


        return cache_project, items
