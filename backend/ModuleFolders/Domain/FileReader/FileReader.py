import importlib
import os
import platform
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Type

from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import ProjectType

if TYPE_CHECKING:
    from ModuleFolders.Domain.FileReader.BaseReader import BaseSourceReader


# ----------------------------------------------------------------------------
# 惰性注册项
# ----------------------------------------------------------------------------
# 旧版 FileReader 在模块顶层 import 了 20+ 个具体 Reader，这会在应用启动时连带
# 加载 python-docx / openpyxl / ebooklib / babeldoc / mediapipe 等重型依赖，导致
# “正在加载文件读写器…” 阶段非常慢。
#
# 现在改为按需加载：FileReader.__init__ 只在字典里登记 (project_type -> 加载器)，
# 真正需要某个 Reader 时（read_files / AutoType 解析）才 import 对应模块。
# ----------------------------------------------------------------------------


class _ReaderEntry:
    """惰性 Reader 注册项。模块在第一次实际使用时才 import。"""

    __slots__ = ("project_type", "_loader", "_init_kwargs_factory", "_cached_class")

    def __init__(
        self,
        project_type: str,
        loader: Callable[[], Type["BaseSourceReader"]],
        init_kwargs_factory: Optional[Callable[[], dict]] = None,
    ):
        self.project_type = project_type
        self._loader = loader
        self._init_kwargs_factory = init_kwargs_factory
        self._cached_class: Optional[Type["BaseSourceReader"]] = None

    def get_class(self) -> Type["BaseSourceReader"]:
        if self._cached_class is None:
            self._cached_class = self._loader()
        return self._cached_class

    def resolve_factory(self):
        """返回一个绑定好初始化参数的 factory（class 或 partial）。"""
        cls = self.get_class()
        kwargs = self._init_kwargs_factory() if self._init_kwargs_factory else None
        return partial(cls, **kwargs) if kwargs else cls


def _module_loader(module_path: str, class_name: str) -> Callable[[], type]:
    def _load():
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    return _load


def _is_windows() -> bool:
    return platform.system() == "Windows"


# 内置 Reader 的惰性注册表：(project_type, module_path, class_name, supported_predicate)
# supported_predicate 为 None 表示始终支持。这里没有调用 is_environ_supported()，
# 因为那需要先 import 模块，违背懒加载的初衷。仅有的平台相关 Reader（Office）
# 用 _is_windows 显式声明。
_BUILTIN_READERS: list[tuple] = [
    (ProjectType.TXT, "ModuleFolders.Domain.FileReader.TxtReader", "TxtReader", None),
    (ProjectType.EPUB, "ModuleFolders.Domain.FileReader.EpubReader", "EpubReader", None),
    (ProjectType.DOCX, "ModuleFolders.Domain.FileReader.DocxReader", "DocxReader", None),
    (ProjectType.SRT, "ModuleFolders.Domain.FileReader.SrtReader", "SrtReader", None),
    (ProjectType.VTT, "ModuleFolders.Domain.FileReader.VttReader", "VttReader", None),
    (ProjectType.LRC, "ModuleFolders.Domain.FileReader.LrcReader", "LrcReader", None),
    (ProjectType.ASS, "ModuleFolders.Domain.FileReader.AssReader", "AssReader", None),
    (ProjectType.MD, "ModuleFolders.Domain.FileReader.MdReader", "MdReader", None),
    (ProjectType.TPP, "ModuleFolders.Domain.FileReader.TPPReader", "TPPReader", None),
    (ProjectType.WOLF_XLSX, "ModuleFolders.Domain.FileReader.WolfXlsxReader", "WolfXlsxReader", None),
    (ProjectType.TRANS, "ModuleFolders.Domain.FileReader.TransReader", "TransReader", None),
    (ProjectType.MTOOL, "ModuleFolders.Domain.FileReader.MToolReader", "MToolReader", None),
    (ProjectType.RENPY, "ModuleFolders.Domain.FileReader.RenpyReader", "RenpyReader", None),
    (ProjectType.VNT, "ModuleFolders.Domain.FileReader.VntReader", "VntReader", None),
    (ProjectType.I18NEXT, "ModuleFolders.Domain.FileReader.I18nextReader", "I18nextReader", None),
    (ProjectType.PO, "ModuleFolders.Domain.FileReader.PoReader", "PoReader", None),
    (ProjectType.PARATRANZ, "ModuleFolders.Domain.FileReader.ParatranzReader", "ParatranzReader", None),
    (ProjectType.OFFICE_CONVERSION_DOC,
     "ModuleFolders.Domain.FileReader.OfficeConversionReader", "OfficeConversionDocReader",
     _is_windows),
    (ProjectType.BABELDOC_PDF, "ModuleFolders.Domain.FileReader.BabeldocPdfReader", "BabeldocPdfReader", None),
    (ProjectType.CSV, "ModuleFolders.Domain.FileReader.CsvReader", "CsvReader", None),
    (ProjectType.PPTX, "ModuleFolders.Domain.FileReader.PptxReader", "PptxReader", None),
    (ProjectType.XLSX, "ModuleFolders.Domain.FileReader.XlsxReader", "XlsxReader", None),
]


# 文件读取器(分发入口)
class FileReader():
    def __init__(self):
        self.reader_factory_dict: dict[str, _ReaderEntry] = {}
        self._auto_type_verified = False
        self._register_system_reader()

    # 初始化时，注册所有内置支持的文件/项目类型（只登记元数据，不 import 模块）。
    def _register_system_reader(self):
        for project_type, module_path, class_name, predicate in _BUILTIN_READERS:
            if predicate is not None and not predicate():
                continue
            self.reader_factory_dict[project_type] = _ReaderEntry(
                project_type, _module_loader(module_path, class_name)
            )

        # AutoType: 注册一个惰性条目，第一次使用时再 import AutoTypeReader，
        # 并解析所有具体 Reader 工厂作为初始化参数。
        self.reader_factory_dict[ProjectType.AUTO_TYPE] = _ReaderEntry(
            ProjectType.AUTO_TYPE,
            _module_loader("ModuleFolders.Domain.FileReader.AutoTypeReader", "AutoTypeReader"),
            init_kwargs_factory=self._build_auto_type_init_kwargs,
        )

    def _build_auto_type_init_kwargs(self) -> dict:
        """AutoType 第一次实例化时调用，按需加载并组装所有具体 Reader 工厂。"""
        concrete_factories = []
        for project_type, entry in self.reader_factory_dict.items():
            if project_type == ProjectType.AUTO_TYPE:
                continue
            concrete_factories.append(entry.resolve_factory())
        # 歧义检验只在首次使用 AutoType 时执行一次，而不是启动时
        if not self._auto_type_verified:
            from ModuleFolders.Domain.FileReader.AutoTypeReader import AutoTypeReader
            AutoTypeReader.verify_reader_factories(concrete_factories)
            self._auto_type_verified = True
        return {"reader_factories": concrete_factories}

    def register_reader(self, reader_class: Type["BaseSourceReader"], **init_kwargs):
        """公共注册 API（兼容已加载的 reader_class，如插件）。"""
        if not reader_class.is_environ_supported():
            return
        # reader_class 已经被调用方 import 过，直接构建一个即时 entry
        kwargs = init_kwargs or None
        ikfn = (lambda kw=kwargs: kw) if kwargs else None
        self.reader_factory_dict[reader_class.get_project_type()] = _ReaderEntry(
            reader_class.get_project_type(),
            (lambda cls=reader_class: cls),
            init_kwargs_factory=ikfn,
        )

    def _get_reader_init_params(self, project_type, label_input_path):
        # 这些类型在 BaseReader 中定义，BaseReader 又会顺带 import mediapipe 等，
        # 因此推迟到 read_files 真正调用时才 import。
        from ModuleFolders.Domain.FileReader.BaseReader import InputConfig, ReaderInitParams

        input_config = InputConfig(Path(label_input_path))
        if project_type == ProjectType.AUTO_TYPE:
            reader_init_params_factory = partial(self._get_reader_init_params, label_input_path=label_input_path)
            return ReaderInitParams(input_config=input_config, reader_init_params_factory=reader_init_params_factory)
        return ReaderInitParams(input_config=input_config)

    # 根据文件类型读取文件，并返回缓存对象
    def read_files(self, translation_project, label_input_path, exclude_rule_str):
        # 检查传入的项目类型是否已经被注册。
        if translation_project in self.reader_factory_dict:
            from ModuleFolders.Domain.FileReader.DirectoryReader import DirectoryReader

            entry = self.reader_factory_dict[translation_project]
            base_factory = entry.resolve_factory()  # 触发该 Reader 的真正 import

            # 获取初始化参数
            reader_init_params = self._get_reader_init_params(translation_project, label_input_path)
            # 绑定配置，使工厂变成无参
            reader_factory = partial(base_factory, **reader_init_params)
            # 创建对象，接收配置好、无参数的 reader_factory
            reader = DirectoryReader(reader_factory, exclude_rule_str.split(','))
            # 再次获取路径对象
            source_directory = Path(label_input_path)
            # 读取整个输入目录,生成缓存对象
            cache_list = reader.read_source_directory(source_directory)
        elif translation_project == "Ainiee_cache":
            cache_list = self.read_cache_files(folder_path=label_input_path)
        return cache_list

    # 读取缓存文件
    def read_cache_files(self, folder_path):
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
        return CacheManager.read_from_file(json_file_path)

    def get_support_project_types(self) -> list[str]:
        # 把自动检测类型放到第一个
        return [
            ProjectType.AUTO_TYPE,
            *(project_type for project_type in self.reader_factory_dict.keys() if project_type != ProjectType.AUTO_TYPE)
        ]
