import platform
import shutil
from pathlib import Path

from ModuleFolders.Cache.CacheItem import CacheItem
from ModuleFolders.FileConverter.OfficeFileConverter import OfficeFileConverter
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig
)
from ModuleFolders.FileOutputer.DocxWriter import DocxWriter


class OfficeConversionWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig, tmp_directory='office_cache'):
        super().__init__(output_config)
        self.tmp_directory = tmp_directory
        self.tmp_file_suffix = '.docx'

        self.docx_writer = DocxWriter(output_config)
        self.converter = OfficeFileConverter()

    def __enter__(self):
        self.docx_writer.__enter__()
        self.converter.__enter__()
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        self.converter.__exit__(exc_type, exc, exc_tb)
        self.docx_writer.__exit__(exc_type, exc, exc_tb)
        output_temp_root = self.output_config.translated_config.output_root / self.tmp_directory
        if output_temp_root.exists():
            shutil.rmtree(output_temp_root)
        input_temp_root = self.output_config.input_root / self.tmp_directory
        if input_temp_root.exists():
            shutil.rmtree(input_temp_root)

    @classmethod
    def get_project_type(cls) -> str:
        return "OfficeConversion"

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        rel_path = translation_file_path.relative_to(self.output_config.translated_config.output_root)
        tmp_source_docx_path = (
            self.output_config.input_root / self.tmp_directory / rel_path
        ).with_suffix(self.tmp_file_suffix)

        # 转换的原文中间格式文件不存在则创建
        if self.converter.can_convert(source_file_path, tmp_source_docx_path):
            if not tmp_source_docx_path.exists():
                self.converter.convert_file(source_file_path, tmp_source_docx_path)

        # 存在转换后原文中间格式文件时进行翻译，并转换回原格式
        if tmp_source_docx_path.exists():
            tmp_translation_docx_path = (
                self.output_config.translated_config.output_root / self.tmp_directory / rel_path
            ).with_suffix(self.tmp_file_suffix)
            if not tmp_translation_docx_path.parent.exists():
                tmp_translation_docx_path.parent.mkdir(parents=True)
            # 翻译中间格式文件
            self.docx_writer.write_translated_file(tmp_translation_docx_path, items, tmp_source_docx_path)
            if self.converter.can_convert(tmp_translation_docx_path, translation_file_path):
                self.converter.convert_file(tmp_translation_docx_path, translation_file_path)

    @classmethod
    def is_environ_supported(cls) -> bool:
        return platform.system() == 'Windows'


class OfficeConversionPdfWriter(OfficeConversionWriter):
    @classmethod
    def get_project_type(cls) -> str:
        return "OfficeConversionPdf"


class OfficeConversionDocWriter(OfficeConversionWriter):
    @classmethod
    def get_project_type(cls) -> str:
        return "OfficeConversionDoc"
