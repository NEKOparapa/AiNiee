import importlib
import platform
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Type

from ModuleFolders.Service.Cache.CacheProject import CacheProject, ProjectType

if TYPE_CHECKING:
    from ModuleFolders.Domain.FileOutputer.BaseWriter import BaseTranslationWriter


# ----------------------------------------------------------------------------
# 惰性注册项
# ----------------------------------------------------------------------------
# 与 FileReader 类似，旧版 FileOutputer 在模块顶层 import 了所有具体 Writer，会
# 把 python-docx / openpyxl / ebooklib / babeldoc / python-pptx 等重型依赖一次性
# 加载，拖慢应用启动。
#
# 现在改为按需加载：FileOutputer.__init__ 只登记 (project_type -> 加载器)，真正
# 输出时才 import 对应模块。
# ----------------------------------------------------------------------------


class _WriterEntry:
    """惰性 Writer 注册项。模块在第一次实际使用时才 import。"""

    __slots__ = ("project_type", "_loader", "_init_kwargs_factory", "_cached_class")

    def __init__(
        self,
        project_type: str,
        loader: Callable[[], Type["BaseTranslationWriter"]],
        init_kwargs_factory: Optional[Callable[[], dict]] = None,
    ):
        self.project_type = project_type
        self._loader = loader
        self._init_kwargs_factory = init_kwargs_factory
        self._cached_class: Optional[Type["BaseTranslationWriter"]] = None

    def get_class(self) -> Type["BaseTranslationWriter"]:
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


# 内置 Writer 的惰性注册表：(project_type, module_path, class_name, supported_predicate)
# supported_predicate 为 None 表示始终支持。
_BUILTIN_WRITERS: list[tuple] = [
    (ProjectType.MTOOL, "ModuleFolders.Domain.FileOutputer.MToolWriter", "MToolWriter", None),
    (ProjectType.SRT, "ModuleFolders.Domain.FileOutputer.SrtWriter", "SrtWriter", None),
    (ProjectType.VTT, "ModuleFolders.Domain.FileOutputer.VttWriter", "VttWriter", None),
    (ProjectType.LRC, "ModuleFolders.Domain.FileOutputer.LrcWriter", "LrcWriter", None),
    (ProjectType.VNT, "ModuleFolders.Domain.FileOutputer.VntWriter", "VntWriter", None),
    (ProjectType.ASS, "ModuleFolders.Domain.FileOutputer.AssWriter", "AssWriter", None),
    (ProjectType.TXT, "ModuleFolders.Domain.FileOutputer.TxtWriter", "TxtWriter", None),
    (ProjectType.MD, "ModuleFolders.Domain.FileOutputer.MdWriter", "MdWriter", None),
    (ProjectType.EPUB, "ModuleFolders.Domain.FileOutputer.EpubWriter", "EpubWriter", None),
    (ProjectType.DOCX, "ModuleFolders.Domain.FileOutputer.DocxWriter", "DocxWriter", None),
    (ProjectType.RENPY, "ModuleFolders.Domain.FileOutputer.RenpyWriter", "RenpyWriter", None),
    (ProjectType.TRANS, "ModuleFolders.Domain.FileOutputer.TransWriter", "TransWriter", None),
    (ProjectType.I18NEXT, "ModuleFolders.Domain.FileOutputer.I18nextWriter", "I18nextWriter", None),
    (ProjectType.PO, "ModuleFolders.Domain.FileOutputer.PoWriter", "PoWriter", None),
    (ProjectType.PARATRANZ, "ModuleFolders.Domain.FileOutputer.ParatranzWriter", "ParatranzWriter", None),
    (ProjectType.TPP, "ModuleFolders.Domain.FileOutputer.TPPWriter", "TPPWriter", None),
    (ProjectType.WOLF_XLSX, "ModuleFolders.Domain.FileOutputer.WolfXlsxWriter", "WolfXlsxWriter", None),
    (ProjectType.OFFICE_CONVERSION_DOC,
     "ModuleFolders.Domain.FileOutputer.OfficeConversionWriter", "OfficeConversionDocWriter",
     _is_windows),
    (ProjectType.BABELDOC_PDF, "ModuleFolders.Domain.FileOutputer.BabeldocPdfWriter", "BabeldocPdfWriter", None),
    (ProjectType.CSV, "ModuleFolders.Domain.FileOutputer.CsvWriter", "CsvWriter", None),
    (ProjectType.PPTX, "ModuleFolders.Domain.FileOutputer.PptxWriter", "PptxWriter", None),
    (ProjectType.XLSX, "ModuleFolders.Domain.FileOutputer.XlsxWriter", "XlsxWriter", None),
]


# 文件输出器
class FileOutputer:

    def __init__(self):
        self.writer_factory_dict: dict[str, _WriterEntry] = {}
        self._register_system_writer()

    def _register_system_writer(self):
        for project_type, module_path, class_name, predicate in _BUILTIN_WRITERS:
            if predicate is not None and not predicate():
                continue
            self.writer_factory_dict[project_type] = _WriterEntry(
                project_type, _module_loader(module_path, class_name)
            )

        # AutoType: 注册一个惰性条目，第一次使用时再 import AutoTypeWriter，
        # 并解析所有具体 Writer 工厂作为初始化参数。
        self.writer_factory_dict[ProjectType.AUTO_TYPE] = _WriterEntry(
            ProjectType.AUTO_TYPE,
            _module_loader("ModuleFolders.Domain.FileOutputer.AutoTypeWriter", "AutoTypeWriter"),
            init_kwargs_factory=self._build_auto_type_init_kwargs,
        )

    def _build_auto_type_init_kwargs(self) -> dict:
        """AutoType 第一次实例化时调用，按需加载并组装所有具体 Writer 工厂。"""
        concrete_factories = []
        for project_type, entry in self.writer_factory_dict.items():
            if project_type == ProjectType.AUTO_TYPE:
                continue
            concrete_factories.append(entry.resolve_factory())
        return {"writer_factories": concrete_factories}

    def register_writer(self, writer_class: Type["BaseTranslationWriter"], **init_kwargs):
        """公共注册 API（兼容已加载的 writer_class，如插件）。"""
        if not writer_class.is_environ_supported():
            return
        kwargs = init_kwargs or None
        ikfn = (lambda kw=kwargs: kw) if kwargs else None
        self.writer_factory_dict[writer_class.get_project_type()] = _WriterEntry(
            writer_class.get_project_type(),
            (lambda cls=writer_class: cls),
            init_kwargs_factory=ikfn,
        )

    # 输出已经翻译文件
    def output_translated_content(self, cache_data: CacheProject, output_path, input_path, config: dict) -> None:
        project_type = cache_data.project_type
        if project_type in self.writer_factory_dict:
            from ModuleFolders.Domain.FileOutputer.DirectoryWriter import DirectoryWriter

            entry = self.writer_factory_dict[project_type]
            base_factory = entry.resolve_factory()  # 触发该 Writer 的真正 import

            writer_iinit_params = self._get_writer_init_params(
                project_type, Path(output_path), Path(input_path), config
            )
            # 绑定配置，使工厂变成无参
            writer_factory = partial(base_factory, **writer_iinit_params)

            # 正确处理输入路径是文件的情况
            input_path_obj = Path(input_path)
            if input_path_obj.is_file():
                source_directory = input_path_obj.parent  # 获取文件所在目录
            else:
                source_directory = input_path_obj

            writer = DirectoryWriter(writer_factory)
            # 为防止双语输出路径被覆盖，这里不传translation_directory
            writer.write_translation_directory(cache_data, source_directory)

    def _get_writer_init_params(self, project_type, output_path: Path, input_path: Path, config: dict):
        # 推迟 BaseWriter 等 import 到这里，避免启动时被拉入。
        from ModuleFolders.Domain.FileOutputer.BaseWriter import WriterInitParams

        output_config = self._get_writer_default_config(project_type, output_path, input_path, config)
        if project_type == ProjectType.AUTO_TYPE:
            writer_init_params_factory = partial(
                self._get_writer_init_params,
                output_path=output_path,
                input_path=input_path,
                config=config,
            )
            # 实际writer默认的输出目录、文件名后缀等配置会被AutoTypeWriter的覆盖
            return WriterInitParams(output_config=output_config, writer_init_params_factory=writer_init_params_factory)
        return WriterInitParams(output_config=output_config)

    def _get_writer_default_config(self, project_type, output_path: Path, input_path: Path, config: dict):
        from ModuleFolders.Domain.FileOutputer.BaseWriter import (
            BilingualOrder, OutputConfig, OutputLanguageConfig, TranslationOutputConfig,
        )

        # 从配置中读取后缀，如果未配置则使用默认值
        translated_suffix = config.get("translated_suffix", "_translated")
        bilingual_suffix = config.get("bilingual_suffix", "_bilingual")

        # 从配置中读取双语排序
        bilingual_order_str = config.get("bilingual_order", "source_first")
        try:
            bilingual_order = BilingualOrder(bilingual_order_str)
        except ValueError:
            # 如果配置值无效，则回退到默认值
            bilingual_order = BilingualOrder.SOURCE_FIRST

        default_translated_config = TranslationOutputConfig(True, translated_suffix, output_path)

        # 创建基础的 OutputConfig，包含新的配置项
        def create_output_config(**kwargs):
            base_args = {
                "bilingual_order": bilingual_order,
                "input_root": input_path,
                "language_config": OutputLanguageConfig(
                    source_language=config.get("source_language"),
                    target_language=config.get("target_language"),
                ),
            }
            base_args.update(kwargs)
            return OutputConfig(**base_args)

        if project_type == ProjectType.SRT:
            return create_output_config(
                translated_config=TranslationOutputConfig(True, config.get("translated_suffix", ".translated"), output_path),
                bilingual_config=TranslationOutputConfig(True, config.get("bilingual_suffix", '.bilingual'), output_path / "bilingual_srt"),
            )
        elif project_type in (ProjectType.TXT, ProjectType.EPUB, ProjectType.BABELDOC_PDF):
            bilingual_dir_map = {
                ProjectType.TXT: "bilingual_txt",
                ProjectType.EPUB: "bilingual_epub",
                ProjectType.BABELDOC_PDF: "bilingual_pdf",
            }
            return create_output_config(
                translated_config=default_translated_config,
                bilingual_config=TranslationOutputConfig(True, bilingual_suffix, output_path / bilingual_dir_map[project_type]),
            )
        elif project_type == ProjectType.AUTO_TYPE:
            return create_output_config(
                translated_config=default_translated_config,
                bilingual_config=TranslationOutputConfig(True, bilingual_suffix, output_path / "bilingual_auto"),
                input_root=None  # AutoTypeWriter 的 input_root 是动态的
            )
        elif project_type in (ProjectType.RENPY, ProjectType.TRANS, ProjectType.TPP):
            # 这些类型通常没有后缀
            return create_output_config(translated_config=TranslationOutputConfig(True, "", output_path))
        else:
            return create_output_config(translated_config=default_translated_config)
