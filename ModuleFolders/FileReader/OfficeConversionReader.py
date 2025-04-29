import platform
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileConverter.OfficeFileConverter import OfficeFileConverter
from ModuleFolders.FileReader.BaseReader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)
from ModuleFolders.FileReader.DocxReader import DocxReader


class OfficeConversionReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig, tmp_directory='office_cache') -> None:
        super().__init__(input_config)
        self.tmp_directory = tmp_directory
        self.tmp_file_type = '.docx'

        self.docx_reader = DocxReader(input_config)
        self.converter = OfficeFileConverter()

    def __enter__(self):
        self.docx_reader.__enter__()
        self.converter.__enter__()
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        self.converter.__exit__(exc_type, exc, exc_tb)
        self.docx_reader.__exit__(exc_type, exc, exc_tb)

    def read_source_file(self, file_path: Path) -> CacheFile:
        rel_path = file_path.relative_to(self.input_config.input_root)
        tmp_docx_path = (
            self.input_config.input_root / self.tmp_directory / rel_path
        ).with_suffix(self.tmp_file_type)
        if self.converter.can_convert(file_path, tmp_docx_path):
            if not tmp_docx_path.exists():
                self.converter.convert_file(file_path, tmp_docx_path)
            return self.docx_reader.read_source_file(tmp_docx_path)
        return CacheFile()

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        # 重载抽象方法，实际不需要使用
        raise NotImplementedError

    @classmethod
    def is_environ_supported(cls) -> bool:
        return platform.system() == 'Windows'

    @property
    def exclude_rules(self) -> list[str]:
        return [f'{self.tmp_directory}/*']


class OfficeConversionPdfReader(OfficeConversionReader):
    @property
    def support_file(self) -> str:
        return 'pdf'

    @classmethod
    def get_project_type(cls) -> str:
        return ProjectType.OFFICE_CONVERSION_PDF


class OfficeConversionDocReader(OfficeConversionReader):
    @property
    def support_file(self) -> str:
        return 'doc'

    @classmethod
    def get_project_type(cls) -> str:
        return ProjectType.OFFICE_CONVERSION_DOC
