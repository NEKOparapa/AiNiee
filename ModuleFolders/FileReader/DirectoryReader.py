import fnmatch
from collections import defaultdict
from pathlib import Path
from typing import Callable

from ModuleFolders.Cache.CacheItem import CacheItem
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
        # 按文件分组源文字
        source_texts = defaultdict(list[str])

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
                                source_texts[cache_file.storage_path].append(item.source_text)

                        if cache_file.items:
                            cache_project.add_file(cache_file)

        # 处理语言统计结果
        language_counter = {}
        low_confidence_language_counter = {}

        for file_path, lang_stats in language_stats.items():
            # 只有存在有效项目的文件才进行处理
            if file_valid_items_count[file_path] > 0:
                high_threshold = file_valid_items_count[file_path] * 0.1  # 有效项目总数的10%
                low_threshold = file_valid_items_count[file_path] * 0.01  # 有效项目总数的1%

                # 先计算所有语言的平均置信度
                all_langs = []
                for lang, (count, total_confidence) in lang_stats.items():
                    avg_confidence = total_confidence / count
                    all_langs.append((lang, count, avg_confidence))

                # 按出现次数降序排序，相同次数按置信度降序排序
                sorted_langs = sorted(all_langs, key=lambda x: (-x[1], -x[2]))

                # 筛选高置信度语言
                high_confidence_langs = []
                for lang, count, avg_confidence in sorted_langs:
                    # 应用筛选条件：次数超过阈值且平均置信度大于等于0.82
                    if count >= high_threshold and avg_confidence >= 0.82:
                        high_confidence_langs.append((lang, count, avg_confidence))

                # 如果没有满足高置信度条件的语言，检查是否有出现次数>1且平均置信度>=0.92的语言
                if not high_confidence_langs:
                    high_confidence_alt_langs = []
                    for lang, count, avg_confidence in sorted_langs:
                        if count > 1 and avg_confidence >= 0.92:
                            high_confidence_alt_langs.append((lang, count, avg_confidence))

                    if high_confidence_alt_langs:
                        language_counter[file_path] = high_confidence_alt_langs
                    else:
                        # 如果到这里了还没有high_confidence_langs的结果，使用mp对所有有效文字进行检测
                        mp_langs, mp_score, _ = ReaderUtil.detect_language_with_mediapipe(
                            [CacheItem(source_text='\n'.join(source_texts[file_path]))], 0, None
                        )[0]
                        if mp_score >= 0.92:
                            # 添加到language_counter
                            language_counter[file_path] = [(mp_langs[0], len(source_texts[file_path]), mp_score)]

                            # 将检测到的语言从sorted_langs中删除
                            sorted_langs = [lang_item for lang_item in sorted_langs if lang_item[0] != mp_langs[0]]
                else:
                    language_counter[file_path] = high_confidence_langs

                # 筛选低置信度语言
                low_confidence_langs = []
                for lang, count, avg_confidence in sorted_langs:
                    # 应用筛选条件：出现次数大于等于低阈值或者平均置信度大于等于0.3小于0.8
                    if low_threshold <= count < high_threshold or (count > 1 and 0.3 <= avg_confidence < 0.8):
                        low_confidence_langs.append((lang, count, avg_confidence))

                if low_confidence_langs:
                    low_confidence_language_counter[file_path] = low_confidence_langs

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
        # 添加低置信度语言统计
        for file_path, langs in low_confidence_language_counter.items():
            cache_project.get_file(file_path).lc_language_stats = langs

        # 释放语言检测器
        ReaderUtil.close_lang_detector()

        return cache_project
