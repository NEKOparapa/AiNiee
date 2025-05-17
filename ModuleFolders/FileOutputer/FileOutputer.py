from functools import partial
from pathlib import Path
from typing import Type

from ModuleFolders.Cache.CacheProject import CacheProject
from ModuleFolders.FileOutputer.AutoTypeWriter import AutoTypeWriter
from ModuleFolders.FileOutputer.BaseWriter import BaseTranslationWriter, OutputConfig, TranslationOutputConfig, WriterInitParams
from ModuleFolders.FileOutputer.DirectoryWriter import DirectoryWriter
from ModuleFolders.FileOutputer.MToolWriter import MToolWriter
from ModuleFolders.FileOutputer.OfficeConversionWriter import OfficeConversionDocWriter
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
from ModuleFolders.FileOutputer.I18nextWriter import I18nextWriter
from ModuleFolders.FileOutputer.BabeldocPdfWriter import BabeldocPdfWriter


# 文件输出器
class FileOutputer:

    def __init__(self):
        self.writer_factory_dict = {}
        self._register_system_writer()

    def register_writer(self, writer_class: Type[BaseTranslationWriter], **init_kwargs):
        """如果writer可注册，则根据project_type进行注册"""
        if writer_class.is_environ_supported():
            writer_factory = partial(writer_class, **init_kwargs) if init_kwargs else writer_class
            self.writer_factory_dict[writer_class.get_project_type()] = writer_factory

    def _register_system_writer(self):
        self.register_writer(MToolWriter)
        self.register_writer(SrtWriter)
        self.register_writer(VttWriter)
        self.register_writer(LrcWriter)
        self.register_writer(VntWriter)
        self.register_writer(TxtWriter)
        self.register_writer(MdWriter)
        self.register_writer(EpubWriter)
        self.register_writer(DocxWriter)
        self.register_writer(RenpyWriter)
        self.register_writer(TransWriter)
        self.register_writer(I18nextWriter)
        self.register_writer(ParatranzWriter)
        self.register_writer(TPPWriter)
        self.register_writer(OfficeConversionDocWriter)
        self.register_writer(BabeldocPdfWriter)

        # 由于values是引用，最先注册和最后注册都一样
        self.register_writer(AutoTypeWriter, writer_factories=self.writer_factory_dict.values())

    # 输出已经翻译文件
    def output_translated_content(self, cache_data: CacheProject, output_path, input_path) -> None:
        # cache_data_iter = iter(cache_data)
        # base_info = next(cache_data_iter)
        project_type = cache_data.project_type
        if project_type in self.writer_factory_dict:
            writer_iinit_params = self._get_writer_init_params(project_type, Path(output_path), Path(input_path))
            # 绑定配置，使工厂变成无参
            writer_factory = partial(self.writer_factory_dict[project_type], **writer_iinit_params)
            source_directory = Path(input_path)
            writer = DirectoryWriter(writer_factory)
            # 为防止双语输出路径被覆盖，这里不传translation_directory
            writer.write_translation_directory(cache_data, source_directory)

    def _get_writer_init_params(self, project_type, output_path: Path, input_path: Path):
        output_config = self._get_writer_default_config(project_type, output_path, input_path)
        if project_type == AutoTypeWriter.get_project_type():
            writer_init_params_factory = partial(
                self._get_writer_init_params,
                output_path=output_path,
                input_path=input_path,
            )
            # 实际writer默认的输出目录、文件名后缀等配置会被AutoTypeWriter的覆盖
            return WriterInitParams(output_config=output_config, writer_init_params_factory=writer_init_params_factory)
        return WriterInitParams(output_config=output_config)

    def _get_writer_default_config(self, project_type, output_path: Path, input_path: Path):
        default_translated_config = TranslationOutputConfig(True, "_translated", output_path)
        if project_type == SrtWriter.get_project_type():
            return OutputConfig(
                TranslationOutputConfig(True, ".translated", output_path),
                TranslationOutputConfig(True, '.bilingual', output_path / "bilingual_srt"),
                input_path
            )
        elif project_type == TxtWriter.get_project_type():
            return OutputConfig(
                default_translated_config,
                TranslationOutputConfig(True, "_bilingual", output_path / "bilingual_txt"),
                input_path
            )
        elif project_type == EpubWriter.get_project_type():
            return OutputConfig(
                default_translated_config,
                TranslationOutputConfig(True, "_bilingual", output_path / "bilingual_epub"),
                input_path
            )
        elif project_type == BabeldocPdfWriter.get_project_type():
            return OutputConfig(
                default_translated_config,
                TranslationOutputConfig(True, "_bilingual", output_path / "bilingual_pdf"),
                input_path
            )
        elif project_type == AutoTypeWriter.get_project_type():
            return OutputConfig(
                default_translated_config,
                TranslationOutputConfig(True, "_bilingual", output_path / "bilingual_auto"),
            )
        elif project_type in (
            RenpyWriter.get_project_type(), TransWriter.get_project_type(), TPPWriter.get_project_type()
        ):
            return OutputConfig(TranslationOutputConfig(True, "", output_path), input_root=input_path)
        else:
            return OutputConfig(default_translated_config, input_root=input_path)
