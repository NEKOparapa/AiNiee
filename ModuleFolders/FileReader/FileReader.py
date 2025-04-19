           
import json
import os
from pathlib import Path
from functools import partial
from typing import Type

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileReader.AutoTypeReader import AutoTypeReader
from ModuleFolders.FileReader.BaseReader import BaseSourceReader, InputConfig, ReaderInitParams
from ModuleFolders.FileReader.DirectoryReader import DirectoryReader
from ModuleFolders.FileReader.MToolReader import MToolReader
from ModuleFolders.FileReader.OfficeConversionReader import OfficeConversionDocReader, OfficeConversionPdfReader
from ModuleFolders.FileReader.ParatranzReader import ParatranzReader
from ModuleFolders.FileReader.TPPReader import TPPReader
from ModuleFolders.FileReader.VntReader import VntReader
from ModuleFolders.FileReader.SrtReader import SrtReader
from ModuleFolders.FileReader.VttReader import VttReader
from ModuleFolders.FileReader.LrcReader import LrcReader
from ModuleFolders.FileReader.TxtReader import TxtReader
from ModuleFolders.FileReader.EpubReader import EpubReader
from ModuleFolders.FileReader.DocxReader import DocxReader
from ModuleFolders.FileReader.MdReader import MdReader
from ModuleFolders.FileReader.RenpyReader import RenpyReader
from ModuleFolders.FileReader.TransReader import TransReader


# 文件读取器
class FileReader():
    def __init__(self):
        self.reader_factory_dict = {}  # 工厂地图
        self._register_system_reader()

    # 初始化时，注册所有内置支持的文件/项目类型。
    def _register_system_reader(self):
        self.register_reader(MToolReader)
        self.register_reader(TPPReader)
        self.register_reader(VntReader)
        self.register_reader(SrtReader)
        self.register_reader(VttReader)
        self.register_reader(LrcReader)
        self.register_reader(TxtReader)
        self.register_reader(EpubReader)
        self.register_reader(DocxReader)
        self.register_reader(MdReader)
        self.register_reader(RenpyReader)
        self.register_reader(TransReader)
        self.register_reader(ParatranzReader)
        self.register_reader(OfficeConversionPdfReader)
        self.register_reader(OfficeConversionDocReader)

        # 检验是否有歧义
        AutoTypeReader.verify_reader_factories(self.reader_factory_dict.values())
        # 由于values是引用，最先注册和最后注册都一样
        self.register_reader(AutoTypeReader, reader_factories=self.reader_factory_dict.values())

    def register_reader(self, reader_class: Type[BaseSourceReader], **init_kwargs):
        """如果reader可注册，则根据project_type进行注册"""
        if reader_class.is_environ_supported():
            reader_factory = partial(reader_class, **init_kwargs) if init_kwargs else reader_class
            self.reader_factory_dict[reader_class.get_project_type()] = reader_factory

    def _get_reader_init_params(self, project_type, label_input_path):
        input_config = InputConfig(Path(label_input_path))
        if project_type == AutoTypeReader.get_project_type():
            reader_init_params_factory = partial(self._get_reader_init_params, label_input_path=label_input_path)
            return ReaderInitParams(input_config=input_config, reader_init_params_factory=reader_init_params_factory)
        return ReaderInitParams(input_config=input_config)

    # 根据文件类型读取文件
    def read_files (self,translation_project,label_input_path, exclude_rule_str):
        # 检查传入的项目类型是否已经被注册。
        if translation_project in self.reader_factory_dict:
            # 获取初始化参数
            reader_init_params = self._get_reader_init_params(translation_project, label_input_path)
            # 绑定配置，使工厂变成无参
            reader_factory = partial(self.reader_factory_dict[translation_project], **reader_init_params)
            # 创建对象，接收配置好、无参数的 reader_factory
            reader = DirectoryReader(reader_factory, exclude_rule_str.split(','))
            # 再次获取路径对象
            source_directory = Path(label_input_path)
            # 读取整个目录
            cache_list = reader.read_source_directory(source_directory) 
        elif translation_project == "Ainiee_cache":
            cache_list = self.read_cache_files(folder_path=label_input_path)
        return cache_list


    #读取缓存文件
    def read_cache_files(self,folder_path):
        # 获取文件夹中的所有文件
        files = os.listdir(folder_path)

        # 查找以 "CacheData" 开头且以 ".json" 结尾的文件
        json_files = [file for file in files if file.startswith("AinieeCacheData") and file.endswith(".json")]

        if not json_files:
            print(f"Error: No 'CacheData' JSON files found in folder '{folder_path}'.")
            return None

        # 选择第一个符合条件的 JSON 文件
        json_file_path = os.path.join(folder_path, json_files[0])

        # 读取 JSON 文件内容
        with open(json_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            project = CacheProject(data[0])
            items = [CacheItem(item) for item in data[1:]]
            return (project, items)

    def get_support_project_types(self) -> set[str]:
        return set(self.reader_factory_dict.keys())
