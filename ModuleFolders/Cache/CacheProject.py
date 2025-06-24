import time
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from ModuleFolders.Cache.BaseCache import ExtraMixin, ThreadSafeCache
from ModuleFolders.Cache.CacheFile import CacheFile


class ProjectType:
    AUTO_TYPE = "AutoType"
    DOCX = "Docx"
    EPUB = "Epub"
    LRC = "Lrc"
    MD = "Md"
    MTOOL = "Mtool"
    OFFICE_CONVERSION_PDF = "OfficeConversionPdf"
    OFFICE_CONVERSION_DOC = "OfficeConversionDoc"
    PARATRANZ = "Paratranz"
    RENPY = "Renpy"
    SRT = "Srt"
    TPP = "Tpp"
    TRANS = "Trans"
    TXT = "Txt"
    VNT = "Vnt"
    VTT = "Vtt"
    I18NEXT = "I18next"
    PO = "Po"
    BABELDOC_PDF = "BabeldocPdf"


@dataclass(repr=False)
class CacheProjectStatistics(ThreadSafeCache):
    total_requests: int = 0
    error_requests: int = 0
    start_time: float = field(default_factory=time.time)
    total_line: int = 0
    line: int = 0
    token: int = 0
    total_completion_tokens: int = 0
    time: float = 0.0


@dataclass(repr=False)
class CacheProject(ThreadSafeCache, ExtraMixin):
    project_id: str = ''
    project_type: str = ''
    project_name: str = ''
    stats_data: CacheProjectStatistics = None
    files: dict[str, CacheFile] = field(default_factory=dict)
    detected_encoding: str = "utf-8"
    detected_line_ending: str = "\n"
    extra: dict[str, Any] = field(default_factory=dict)

    # 添加文件
    def add_file(self, file: CacheFile) -> None:
        """线程安全添加文件"""
        with self._lock:
            if hasattr(self, "file_project_types"):
                del self.file_project_types  # 清除缓存
            self.files[file.storage_path] = file

    # 根据相对路径获取文件
    def get_file(self, storage_path: str) -> CacheFile:
        """线程安全获取文件"""
        with self._lock:
            return self.files.get(storage_path)

    def items_iter(self, project_types: str | frozenset[str] = None):
        if isinstance(project_types, str):
            project_types = frozenset([project_types])
        with self._lock:
            for file in self.files.values():
                if project_types is None or file.file_project_type in project_types:
                    for item in file.items:
                        yield item

    def count_items(self, status=None):
        with self._lock:
            if status is None:
                return sum(len(file.items) for file in self.files.values())
            else:
                return sum(
                    1 for item in self.items_iter() if item.translation_status == status
                )

    @cached_property
    def file_project_types(self) -> frozenset[str]:
        with self._lock:
            return frozenset(file.file_project_type for file in self.files.values())

    def _extra(self) -> dict[str, Any]:
        return self.extra
