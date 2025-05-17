import shutil
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileAccessor.BabeldocPdfAccessor import BabeldocPdfAccessor
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class BabeldocPdfWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig, tmp_directory='babeldoc_cache'):
        super().__init__(output_config)
        self.tmp_directory = tmp_directory
        self.abs_tmp_directory = output_config.input_root / self.tmp_directory
        self.file_accessor = BabeldocPdfAccessor(self.abs_tmp_directory, output_config)

    def __enter__(self):
        self.file_accessor.__enter__()
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        self.file_accessor.__exit__(exc_type, exc, exc_tb)
        if self.abs_tmp_directory.exists():
            shutil.rmtree(self.abs_tmp_directory)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_translation_file(
            translation_file_path, cache_file,
            pre_write_metadata, source_file_path, "mono_pdf_path"
        )

    def on_write_bilingual(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        self._write_translation_file(
            translation_file_path, cache_file,
            pre_write_metadata, source_file_path, "dual_pdf_path"
        )

    def _write_translation_file(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path,
        babeldoc_output_attr: str,
    ):
        result = self.file_accessor.write_content(source_file_path, cache_file.items)
        babeldoc_path_str = getattr(result, babeldoc_output_attr)
        if babeldoc_path_str and (babeldoc_path := Path(babeldoc_path_str)).exists():
            if translation_file_path.exists():
                translation_file_path.unlink()
            babeldoc_path.rename(translation_file_path)

    @classmethod
    def get_project_type(self):
        return ProjectType.BABELDOC_PDF
