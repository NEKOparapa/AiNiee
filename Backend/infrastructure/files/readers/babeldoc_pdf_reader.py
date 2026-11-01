from pathlib import Path
from tempfile import TemporaryDirectory

from Backend.domain.models.cache_file import CacheFile
from Backend.domain.models.cache_item import CacheItem
from Backend.domain.models.cache_project import ProjectType
from Backend.infrastructure.files.accessors.babeldoc_pdf_accessor import BabeldocPdfAccessor
from Backend.infrastructure.files.readers.base_reader import (
    BaseSourceReader,
    InputConfig,
    PreReadMetadata
)


class BabeldocPdfReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig, tmp_directory=None, parse_options=None):
        super().__init__(input_config)
        self._temporary = None
        self.file_accessor = None
        self.parse_options = dict(parse_options or {})

    def __enter__(self):
        self._ensure_accessor()
        return self

    def _ensure_accessor(self):
        if self.file_accessor is None:
            self._temporary = TemporaryDirectory(prefix="ainiee-pdf-read-")
            self.file_accessor = BabeldocPdfAccessor(Path(self._temporary.name), None, self.parse_options)

    def __exit__(self, exc_type, exc, exc_tb):
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
            self.file_accessor = None

    @classmethod
    def get_project_type(self):
        return ProjectType.BABELDOC_PDF

    @property
    def support_file(self):
        return 'pdf'

    def on_read_source(self, file_path: Path, pre_read_metadata: PreReadMetadata) -> CacheFile:
        self._ensure_accessor()
        source_texts = self.file_accessor.read_content(file_path)
        return CacheFile(extra={"pdf": self.file_accessor.parse_metadata(source_texts)}, items=[
            CacheItem(source_text=line) for line in source_texts
        ])

    @property
    def exclude_rules(self):
        return []
