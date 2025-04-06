import os
import copy
import json
from functools import partial
from pathlib import Path
from typing import Callable



from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileAccessor.DocxAccessor import DocxAccessor
from ModuleFolders.FileAccessor.EpubAccessor import EpubAccessor
from ModuleFolders.FileOutputer.BaseWriter import BaseTranslationWriter, OutputConfig, TranslationOutputConfig
from ModuleFolders.FileOutputer.DirectoryWriter import DirectoryWriter
from ModuleFolders.FileOutputer.MToolWriter import MToolWriter
from ModuleFolders.FileOutputer.ParatranzWriter import ParatranzWriter
from ModuleFolders.FileOutputer.TPPWriter import TPPWriter
from ModuleFolders.FileOutputer.VntWriter import VntWriter
from ModuleFolders.FileOutputer.SrtWriter import SrtWriter
from ModuleFolders.FileOutputer.VttWriter import VttWriter
from ModuleFolders.FileOutputer.LrcWriter import LrcWriter
from ModuleFolders.FileOutputer.TxtWriter import TxtWriter
from ModuleFolders.FileOutputer.EpubWriter import EpubWriter
from ModuleFolders.FileOutputer.DocxWriter import DocxWriter
from ModuleFolders.FileOutputer.MdWriter import MdWriter
from ModuleFolders.FileOutputer.RenpyWriter import RenpyWriter
from ModuleFolders.FileOutputer.TransWriter import TransWriter




# 文件输出器
class FileOutputer():

    def __init__(self):
        self.writer_factory_dict = {}
        self._register_system_writer()

    # 输出缓存文件
    def output_cache_file(self,cache_data,output_path):
        # 复制缓存数据到新变量
        try:
            modified_cache_data = copy.deepcopy(cache_data)
        except:
            print("[INFO]: 无法正常进行深层复制,改为浅复制")
            modified_cache_data = cache_data.copy()

        # 修改新变量的元素中的'translation_status'
        for item in modified_cache_data:
            if 'translation_status' in item and item['translation_status'] == 2:
                item['translation_status'] = 0

        # 输出为JSON文件
        with open(os.path.join(output_path, "AinieeCacheData.json"), "w", encoding="utf-8") as f:
            json.dump(modified_cache_data, f, ensure_ascii=False, indent=4)

    def register_writer(self, project_type, writer_factory: Callable[[OutputConfig], BaseTranslationWriter]):
        self.writer_factory_dict[project_type] = writer_factory

    # 输出已经翻译文件
    def output_translated_content(self, cache_data, output_path, input_path) -> None:
        cache_data_iter = iter(cache_data)
        project_type = next(cache_data_iter)["project_type"]
        if project_type in self.writer_factory_dict:
            output_config = self._get_writer_default_config(project_type, Path(output_path))
            # 绑定配置，使工厂变成无参
            writer_factory = partial(self.writer_factory_dict[project_type], output_config)
            items = list(map(CacheItem, cache_data_iter))
            source_directory = Path(input_path)
            writer = DirectoryWriter(writer_factory)
            # 为防止双语输出路径被覆盖，这里不传translation_directory
            writer.write_translation_directory(items, source_directory)

    def _register_system_writer(self):
        self.register_writer(MToolWriter.get_project_type(), MToolWriter)
        self.register_writer(SrtWriter.get_project_type(), SrtWriter)
        self.register_writer(VttWriter.get_project_type(), VttWriter)
        self.register_writer(LrcWriter.get_project_type(), LrcWriter)
        self.register_writer(VntWriter.get_project_type(), VntWriter)
        self.register_writer(TxtWriter.get_project_type(), TxtWriter)
        self.register_writer(MdWriter.get_project_type(), MdWriter)
        self.register_writer(EpubWriter.get_project_type(), partial(EpubWriter, file_accessor=EpubAccessor()))
        self.register_writer(DocxWriter.get_project_type(), partial(DocxWriter, file_accessor=DocxAccessor()))
        self.register_writer(RenpyWriter.get_project_type(), RenpyWriter)
        self.register_writer(TransWriter.get_project_type(), TransWriter)
        self.register_writer(ParatranzWriter.get_project_type(), ParatranzWriter)
        self.register_writer(TPPWriter.get_project_type(), TPPWriter)

    def _get_writer_default_config(self, project_type, output_path: Path):
        default_translated_config = TranslationOutputConfig(True, "_translated", output_path)
        if project_type == SrtWriter.get_project_type():
            return OutputConfig(
                TranslationOutputConfig(True, ".translated", output_path),
                TranslationOutputConfig(True, '.bilingual', output_path / "bilingual_srt"),
            )
        elif project_type == TxtWriter.get_project_type():
            return OutputConfig(
                default_translated_config,
                TranslationOutputConfig(True, "_bilingual", output_path / "bilingual_txt"),
            )
        elif project_type == EpubWriter.get_project_type():
            return OutputConfig(
                default_translated_config,
                TranslationOutputConfig(True, "_bilingual", output_path / "bilingual_epub"),
            )
        elif project_type in (
            RenpyWriter.get_project_type(), TransWriter.get_project_type(), TPPWriter.get_project_type()
        ):
            return OutputConfig(TranslationOutputConfig(True, "", output_path))
        else:
            return OutputConfig(default_translated_config)
