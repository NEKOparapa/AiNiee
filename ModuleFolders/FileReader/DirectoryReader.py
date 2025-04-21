import fnmatch
import json
import pathlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Union

import chardet
import charset_normalizer
import langcodes
import rich

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.BaseReader import BaseSourceReader


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

    try:
        cn_result = charset_normalizer.from_path(file_path).best()

        # 如果`charset_normalizer`有检测到结果，直接使用结果
        if cn_result:
            detected_encoding = cn_result.encoding
            confidence = 1.0
        else:
            # 如果没有检测到结果，回退到使用`chardet`
            rich.print(f"[[red]WARNING[/]] 文件 {file_path} 使用`charset_normalizer`检测失败，回退到使用`chardet`检测")

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

    except Exception as e:
        print(f"[[red]ERROR[/]] 文件 {file_path} 检测过程出错: {str(e)}")
        return 'utf-8'  # 出错时返回默认编码


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

        # 语言统计：{file_path: {lang_code: (count, total_confidence)}}
        language_stats = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
        # 每个文件的有效项目总数（排除symbols_only）
        file_valid_items_count = defaultdict(int)

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

                        # 确定要使用的编码
                        encoding_to_use = "utf-8" if detected_encoding.startswith("non_text") else detected_encoding

                        relative_path = str(file_path.relative_to(source_directory))

                        # 保存文件编码信息
                        cache_project.set_file_original_encoding(relative_path, encoding_to_use)

                        # 使用检测到的编码读取文件内容
                        for item in reader.read_source_file(file_path, encoding_to_use):
                            item.set_text_index(text_index)
                            item.set_model('none')
                            item.set_storage_path(relative_path)
                            item.set_file_name(file_path.name)
                            item.set_file_project_type(reader.get_file_project_type(file_path))
                            items.append(item)

                            lang_code = item.get_lang_code()

                            # 只统计非symbols_only的语言
                            if lang_code != "symbols_only":
                                lang_confidence = item.get_lang_confidence()
                                # 更新语言统计：[计数, 累计置信度]
                                stats = language_stats[relative_path][lang_code]
                                stats[0] += 1  # 增加计数
                                stats[1] += lang_confidence  # 累加置信度

                                # 累计有效项目总数
                                file_valid_items_count[relative_path] += 1

                            text_index += 1
                            file_project_types.add(reader.get_file_project_type(file_path))

            # 设置目录下包含的文件项目类型，用于快速判断
            cache_project.set_file_project_types(list(file_project_types))

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

                        # 应用筛选条件：次数超过阈值且平均置信度>=0.6
                        if count >= threshold and avg_confidence >= 0.6:
                            filtered_langs.append((lang, count, avg_confidence))

                    # 按出现次数降序排序，相同次数按语言代码排序
                    if filtered_langs:
                        sorted_langs = sorted(filtered_langs, key=lambda x: (-x[1], x[0]))
                        language_counter[file_path] = sorted_langs

            # 处理未出现在language_counter中的文件
            valid_file_paths = set(file_valid_items_count.keys())
            files_in_counter = set(language_counter.keys())
            missing_files = valid_file_paths - files_in_counter

            # 为未统计到有效语言的文件添加默认值
            for file_path in missing_files:
                # un表示未知语言
                language_counter[file_path] = [('un', 0, -1.0)]

            # 保存（过滤后的）每个文件对应的语言信息
            cache_project.set_file_language_counter(language_counter)

            return cache_project, items
