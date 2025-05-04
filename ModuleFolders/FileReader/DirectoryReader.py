import fnmatch
from collections import  defaultdict
from pathlib import Path
from typing import Callable

from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader import ReaderUtil
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
    def read_source_directory(self, source_directory: Path, source_language: str) -> CacheProject:
        """
        树状读取文件夹内同类型文件，检测每个文件的编码，并在最后设置项目的默认编码。

        Args:
            source_directory: 源文件目录

        Returns:
            CacheProject: 包含项目信息和文件内容
        """
        cache_project = CacheProject()  # 项目头信息
        text_index = 1  # 文本索引

        # 语言统计：{file_path: {lang_code: (count, total_confidence)}}
        language_stats = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
        # 每个文件的有效项目总数（排除symbols_only）
        file_valid_items_count = defaultdict(int)

        with self.create_reader() as reader:
            self._update_exclude_rules(reader.exclude_rules)
            cache_project.project_type = reader.get_project_type()

            for root, _, files in source_directory.walk():  # 递归遍历文件夹
                for file in files:
                    file_path = root / file
                    # 检查是否被排除，以及是否是目标类型文件
                    if not self.is_exclude(file_path, source_directory) and reader.can_read(file_path):

                        # 读取单个文件的文本信息，并添加其他信息
                        cache_file = reader.read_source_file(file_path, source_language)
                        cache_file.storage_path = str(file_path.relative_to(source_directory))
                        cache_file.file_project_type = reader.get_file_project_type(file_path)
                        for item in cache_file.items:
                            item.text_index = text_index
                            item.model = 'none'
                            text_index += 1

                            # 统计每行的语言信息
                            lang_code = item.lang_code
                            # 只统计检测到有效语言代码的item行
                            if lang_code:
                                lang_confidence = lang_code[1]
                                # 更新语言统计：[计数, 累计置信度]
                                stats = language_stats[cache_file.storage_path][lang_code[0]]
                                stats[0] += 1  # 增加计数
                                stats[1] += lang_confidence  # 累加置信度
                                # 累计有效项目总数
                                file_valid_items_count[cache_file.storage_path] += 1
                                
                        if cache_file.items:
                            cache_project.add_file(cache_file)

        # 处理语言统计结果
        language_counter = {}
        for file_path, lang_stats in language_stats.items():
            # 只有存在有效项目的文件才进行处理
            if file_valid_items_count[file_path] > 0:
                threshold = file_valid_items_count[file_path] * 0.2  # 有效项目总数的20%

                # 计算平均置信度并筛选
                filtered_langs = []
                for lang, (count, total_confidence) in lang_stats.items():
                    avg_confidence = total_confidence / count

                    # 应用筛选条件：次数超过阈值且平均置信度>=0.75
                    if count >= threshold and avg_confidence >= 0.75:
                        filtered_langs.append((lang, count, avg_confidence))

                # 按出现次数降序排序，相同次数按语言代码排序
                if filtered_langs:
                    sorted_langs = sorted(filtered_langs, key=lambda x: (-x[1], x[0]))
                    language_counter[file_path] = sorted_langs
                else:
                    # 补充条件：如果没有满足原条件的语言，检查是否有出现次数>1且平均置信度>0.95的语言
                    high_confidence_langs = []
                    for lang, (count, total_confidence) in lang_stats.items():
                        avg_confidence = total_confidence / count
                        if count > 1 and avg_confidence > 0.95:
                            high_confidence_langs.append((lang, count, avg_confidence))

                    if high_confidence_langs:
                        sorted_langs = sorted(high_confidence_langs, key=lambda x: (-x[1], x[0]))
                        language_counter[file_path] = sorted_langs

        # 处理未出现在language_counter中的文件
        valid_file_paths = set(file_valid_items_count.keys())
        files_in_counter = set(language_counter.keys())
        missing_files = valid_file_paths - files_in_counter

        # 为未统计到有效语言的文件添加默认值
        for file_path in missing_files:
            # un表示未知语言
            language_counter[file_path] = [('un', 0, -1.0)]

        # 为对应的CacheFile添加语言统计属性
        for file_path, langs in language_counter.items():
            cache_project.get_file(file_path).language_stats = langs

        # 释放语言检测器
        ReaderUtil.close_lang_detector()

        return cache_project
