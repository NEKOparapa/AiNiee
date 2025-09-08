import fnmatch
from collections import defaultdict
from pathlib import Path
from typing import Callable

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader import ReaderUtil
from ModuleFolders.FileReader.BaseReader import BaseSourceReader
from ModuleFolders.FileReader.ReaderUtil import make_final_detect_text

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
        
        # 只有在 source_directory 有效时才计算相对路径
        if source_directory and source_directory.is_dir():
            try:
                rel_path_str = str(file_path.relative_to(source_directory))
                if any(fnmatch.fnmatch(rel_path_str, pattern) for pattern in self.exclude_paths):
                    return True
            except ValueError:
                # 如果不在同一驱动器或路径下，会引发ValueError，此时认为不排除
                pass
        return False

    # 2025年9月8日增加单文件输入支持
    # 树状读取文件夹内同类型文件
    def read_source_directory(self, input_path: Path) -> CacheProject:
        """
        读取文件夹或单个文件，检测每个文件的编码，并在最后设置项目的默认编码。
        此函数现在支持单个文件路径和目录路径。

        Args:
            input_path: 源文件或目录的路径

        Returns:
            CacheProject: 包含项目信息和文件内容
        """
        cache_project = CacheProject()  # 项目头信息
        text_index = 1  # 文本索引

        # 语言统计：{file_path: {lang_code: (count, total_confidence)}}
        language_stats = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
        file_valid_items_count = defaultdict(int)
        source_texts = defaultdict(list[str])

        # 根据路径类型确定要处理的文件列表和基础目录
        files_to_process = []
        base_directory = None

        # 如果是目录，递归获取所有文件
        if input_path.is_dir():
            base_directory = input_path
            for root, _, files in base_directory.walk():
                for file in files:
                    files_to_process.append(root / file)

        # 如果是单个文件，直接处理该文件
        elif input_path.is_file():
            base_directory = input_path.parent
            files_to_process.append(input_path)

        # 如果路径不存在或不是文件/目录，则返回空项目
        else:
            print(f"Warning: Input path '{input_path}' does not exist or is not a file/directory.")
            return cache_project
        
        # 创建reader实例
        with self.create_reader() as reader:
            self._update_exclude_rules(reader.exclude_rules)
            cache_project.project_type = reader.get_project_type()

            # 遍历预先生成的文件列表
            for file_path in files_to_process:
                # 检查是否被排除，以及是否是目标类型文件
                if not self.is_exclude(file_path, base_directory) and reader.can_read(file_path):
                    
                    # 读取单个文件的文本信息，并添加其他信息
                    cache_file = reader.read_source_file(file_path)
                    #空文件跳过
                    if not cache_file:
                       continue
                       
                    # 使用 base_directory 计算相对路径
                    cache_file.storage_path = str(file_path.relative_to(base_directory))
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
                            stats[0] += 1   # 增加计数
                            stats[1] += lang_confidence   # 累加置信度

                            # 累计有效项目总数
                            file_valid_items_count[cache_file.storage_path] += 1

                            # 添加行至后续使用
                            final_detect_text = make_final_detect_text(item)
                            if final_detect_text:
                                source_texts[cache_file.storage_path].append(final_detect_text)

                    # 补充缺失的字典项
                    if not language_stats[cache_file.storage_path]:
                        language_stats[cache_file.storage_path] = defaultdict(lambda: [0, 0.0])

                    if cache_file.items:
                        cache_project.add_file(cache_file)


        # 处理语言统计结果
        language_counter = defaultdict(list)
        low_confidence_language_counter = defaultdict(list)

        for file_path, lang_stats in language_stats.items():
            # 只有存在有效项目的文件才进行处理
            current_file_items_count = file_valid_items_count[file_path]
            if current_file_items_count > 0:
                high_threshold = max(current_file_items_count * 0.1, min(current_file_items_count, 3))  # 有效项目总数的10%
                mid_threshold = max(current_file_items_count * 0.05, min(current_file_items_count, 2))  # 有效项目总数的5%
                low_threshold = max(current_file_items_count * 0.01, 1)  # 有效项目总数的1%

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
                    if count >= high_threshold and avg_confidence >= 0.82 or \
                            count >= mid_threshold and avg_confidence >= 0.92 or \
                            count >= low_threshold and avg_confidence >= 0.96:
                        high_confidence_langs.append((lang, count, avg_confidence))
                # 获取有效语言列表
                hc_langs_set = {lang for lang, count, avg_confidence in high_confidence_langs}

                # 如果到这里了还没有high_confidence_langs的结果，使用mp对所有有效文字进行检测
                if not high_confidence_langs:
                    if len(source_texts[file_path]) > 0:
                        mp_langs, mp_score, _ = ReaderUtil.detect_language_with_mediapipe(
                            [CacheItem(source_text='\n'.join(source_texts[file_path]))], 0, None
                        )[0]
                        if mp_score >= 0.82:
                            # 添加到language_counter
                            language_counter[file_path] = [(mp_langs[0], len(source_texts[file_path]), mp_score)]

                            # 添加到 hc_langs_set
                            hc_langs_set.add(mp_langs[0])
                    else:
                        language_counter[file_path] = [('un', len(source_texts[file_path]), -1.0)]
                else:
                    language_counter[file_path] = high_confidence_langs

                # 筛选低置信度语言
                low_confidence_langs = []
                for lang, count, avg_confidence in sorted_langs:
                    # 应用筛选条件：出现次数小于高置信度或者平均置信度小于0.82
                    # (count < high_threshold or avg_confidence < 0.82) and
                    if lang not in hc_langs_set:
                        low_confidence_langs.append((lang, count, avg_confidence))

                if low_confidence_langs:
                    low_confidence_language_counter[file_path] = low_confidence_langs
            else:
                language_counter[file_path] = [('un', 0, -1.0)]

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

        # 自动生成工程名字
        self._generate_project_name(cache_project)

        return cache_project


    # 自动生成工程名字方法
    def _generate_project_name(self, cache_project: CacheProject):
        """
        根据读取的文件列表，自动生成工程名字。
        """
        # 配置的参数
        CHARS_PER_FILENAME = 5
        SEPARATOR = '&&'
        MAX_FILES_FOR_NAME = 4

        # 从字典中获取所有 CacheFile 对象，并转换为列表
        files_list = list(cache_project.files.values())

        if not files_list:
            cache_project.project_name = "EmptyProject"
            return

        if len(files_list) == 1:
            # 单个文件：直接使用文件名（不含扩展名）
            # 使用列表索引 [0] 来访问第一个元素
            # 当输入是单个文件时, storage_path 就是文件名
            file_path = Path(files_list[0].storage_path)
            cache_project.project_name = file_path.stem
        else:
            # 多个文件：组合文件名
            name_parts = []
            # 对列表进行切片
            for cache_file in files_list[:MAX_FILES_FOR_NAME]:
                # storage_path 是相对路径，需要从中获取文件名
                file_stem = Path(cache_file.storage_path).stem
                name_parts.append(file_stem[:CHARS_PER_FILENAME])
            
            cache_project.project_name = SEPARATOR.join(name_parts)