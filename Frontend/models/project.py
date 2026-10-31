"""Display objects decoded from the project API, independent of backend classes."""
import copy
import posixpath
from dataclasses import dataclass, field, fields


class Snapshot:
    @classmethod
    def from_dict(cls, data):
        values = {f.name: copy.deepcopy(data[f.name]) for f in fields(cls) if f.name in data}
        return cls(**values)

    def to_dict(self):
        def encode(value):
            if isinstance(value, Snapshot):
                return value.to_dict()
            if isinstance(value, dict):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [encode(item) for item in value]
            return copy.deepcopy(value)
        return {f.name: encode(getattr(self, f.name)) for f in fields(self) if getattr(self, f.name) is not None}

    def get_extra(self, key, default=None):
        return self.extra.get(key, default)


@dataclass
class CacheItem(Snapshot):
    text_index: int = 0
    translation_status: int = 0
    model: str = ""
    source_text: str = ""
    translated_text: str = ""
    text_to_detect: str | None = None
    lang_code: list | None = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.source_text = self.source_text or ""
        self.translated_text = self.translated_text or ""


@dataclass
class CacheFile(Snapshot):
    storage_path: str = ""
    encoding: str = "utf-8"
    file_project_type: str = ""
    line_ending: str = "\n"
    items: list = field(default_factory=list)
    language_stats: list = field(default_factory=list)
    lc_language_stats: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        result = super().from_dict(data)
        result.items = [CacheItem.from_dict(item) for item in data.get("items", [])]
        return result

    @property
    def file_name(self):
        return posixpath.basename(self.storage_path.replace("\\", "/"))

    def get_item(self, text_index):
        return next(item for item in self.items if item.text_index == text_index)

    def index_of(self, text_index):
        return next(i for i, item in enumerate(self.items) if item.text_index == text_index)


@dataclass
class CacheProjectStatistics(Snapshot):
    total_requests: int = 0
    error_requests: int = 0
    start_time: float = 0
    total_line: int = 0
    line: int = 0
    token: int = 0
    total_completion_tokens: int = 0
    time: float = 0


@dataclass
class CacheProject(Snapshot):
    project_id: str = ""
    project_type: str = ""
    project_name: str = ""
    project_create_time: str = ""
    input_path: str = ""
    stats_data: CacheProjectStatistics | None = None
    files: dict = field(default_factory=dict)
    detected_encoding: str = "utf-8"
    detected_line_ending: str = "\n"
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        result = super().from_dict(data)
        result.files = {path: CacheFile.from_dict(value) for path, value in data.get("files", {}).items()}
        if data.get("stats_data") is not None:
            result.stats_data = CacheProjectStatistics.from_dict(data["stats_data"])
        return result

    def get_file(self, path):
        return self.files.get(path)

    def count_items(self, status=None):
        return sum(1 for file in self.files.values() for item in file.items if status is None or item.translation_status == status)
