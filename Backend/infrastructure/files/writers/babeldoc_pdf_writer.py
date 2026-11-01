import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_project import ProjectType
from Backend.infrastructure.files.accessors.babeldoc_pdf_accessor import BabeldocPdfAccessor
from Backend.infrastructure.files.writers.base_writer import (
    BaseBilingualWriter,
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class BabeldocPdfWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig, tmp_directory=None):
        super().__init__(output_config)
        self._temporary = TemporaryDirectory(prefix="ainiee-pdf-write-")
        self.abs_tmp_directory = Path(self._temporary.name)
        self.file_accessor = None

    def __exit__(self, exc_type, exc, exc_tb):
        self._temporary.cleanup()

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
        metadata = cache_file.extra.get("pdf", {})
        if self.file_accessor is None or self.file_accessor.parse_options != metadata.get("parse_options", {}):
            self.file_accessor = BabeldocPdfAccessor(self.abs_tmp_directory, self.output_config, metadata.get("parse_options", {}))
        result = self.file_accessor.write_content(source_file_path, cache_file.items, metadata)
        babeldoc_path_str = getattr(result, babeldoc_output_attr)
        if babeldoc_path_str and (babeldoc_path := Path(babeldoc_path_str)).exists():
            # 确保目标文件夹存在
            if not translation_file_path.parent.exists():
                translation_file_path.parent.mkdir(parents=True, exist_ok=True)
                
            shutil.copyfile(babeldoc_path, translation_file_path)
        else:
            raise RuntimeError("BabelDOC 没有生成所需输出文件")

    @classmethod
    def get_project_type(self):
        return ProjectType.BABELDOC_PDF
