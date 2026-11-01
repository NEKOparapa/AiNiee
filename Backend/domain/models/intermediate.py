"""Versioned public project model and transport-independent batching.

The existing cache dataclasses remain the runtime representation. These schemas
validate their JSON representation without importing readers, Qt, or providers.
"""
import copy
import os
import re
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictInt, StrictStr, ValidationError, field_validator, model_validator

from Backend.application.pipeline_common import PipelineError
from Backend.domain.models.cache_item import CacheItem, TranslationStatus
from Backend.domain.models.cache_project import CacheProject

SCHEMA_VERSION = 2
RETIRED_PROJECT_TYPES = frozenset({"OfficeConversionPdf", "OfficeConversionDoc"})
_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]+\Z")


class ModelSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceReference(ModelSchema):
    path: StrictStr = ""
    sha256: StrictStr = Field(default="", pattern=r"^(?:[0-9a-fA-F]{64})?$")
    verified: bool = False

    @model_validator(mode="after")
    def verified_source_has_hash(self):
        if self.path and ("\x00" in self.path or not (PureWindowsPath(self.path).is_absolute() or PurePosixPath(self.path).is_absolute())):
            raise ValueError("原文件引用必须使用绝对路径")
        if self.verified and (not self.path or not self.sha256):
            raise ValueError("已校验的原文件引用必须包含路径和 SHA256")
        return self


class DocumentLocator(ModelSchema):
    kind: Literal["document"] = "document"
    index: int | None = Field(default=None, ge=0)
    structure_path: str | list[str | int] | None = None


class PdfLocator(ModelSchema):
    kind: Literal["pdf"] = "pdf"
    index: int | None = Field(default=None, ge=0)
    page_index: int | None = Field(default=None, ge=0)
    polygon: list[tuple[float, float]] | None = None


class ImageLocator(ModelSchema):
    kind: Literal["image"] = "image"
    index: int | None = Field(default=None, ge=0)
    page_index: int | None = Field(default=None, ge=0)
    polygon: list[tuple[float, float]] | None = None
    coordinate_space: Literal["pixel"] = "pixel"
    rotation: float | None = None


class AudioLocator(ModelSchema):
    kind: Literal["audio"] = "audio"
    index: int | None = Field(default=None, ge=0)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    speaker_id: str | None = None

    @model_validator(mode="after")
    def valid_interval(self):
        if (self.start_ms is None) != (self.end_ms is None):
            raise ValueError("音频定位需要同时提供 start_ms 和 end_ms")
        if self.start_ms is not None and self.end_ms <= self.start_ms:
            raise ValueError("音频 end_ms 必须大于 start_ms")
        return self


Locator = Annotated[DocumentLocator | PdfLocator | ImageLocator | AudioLocator, Field(discriminator="kind")]


class IntermediateItem(ModelSchema):
    item_id: StrictStr = ""
    locator: Locator | None = None
    text_index: StrictInt = Field(default=0, ge=0)
    translation_status: Literal[0, 1, 2, 7, 8] = 0
    model: StrictStr = ""
    source_text: StrictStr = ""
    translated_text: StrictStr | None = ""
    text_to_detect: StrictStr | None = None
    lang_code: tuple[str, float, list[str]] | None = None
    extra: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("locator", mode="before")
    @classmethod
    def empty_locator(cls, value):
        return None if value == {} else value


class IntermediateFile(ModelSchema):
    file_id: StrictStr = ""
    media_type: Literal["", "document", "pdf", "image", "audio"] = ""
    source_ref: SourceReference = Field(default_factory=SourceReference)
    media_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    storage_path: StrictStr = ""
    encoding: StrictStr = "utf-8"
    file_project_type: StrictStr = ""
    line_ending: StrictStr = "\n"
    items: list[IntermediateItem] = Field(default_factory=list)
    language_stats: list[tuple[str, int, float]] = Field(default_factory=list)
    lc_language_stats: list[tuple[str, int, float]] = Field(default_factory=list)
    extra: dict[str, JsonValue] = Field(default_factory=dict)


class IntermediateStatistics(ModelSchema):
    total_requests: int = 0
    error_requests: int = 0
    start_time: float = 0.0
    total_line: int = 0
    line: int = 0
    token: int = 0
    total_completion_tokens: int = 0
    time: float = 0.0


class TranslationContext(ModelSchema):
    source_language: str = ""
    target_language: str = ""


class IntermediateModel(ModelSchema):
    """The same JSON structure used by the cache and all six pipeline APIs."""
    schema_version: Literal[2] = SCHEMA_VERSION
    translation_context: TranslationContext = Field(default_factory=TranslationContext)
    project_id: StrictStr = ""
    project_type: StrictStr = ""
    project_name: StrictStr = ""
    project_create_time: StrictStr = ""
    input_path: StrictStr = ""
    stats_data: IntermediateStatistics | None = None
    files: dict[str, IntermediateFile] = Field(default_factory=dict)
    detected_encoding: StrictStr = "utf-8"
    detected_line_ending: StrictStr = "\n"
    extra: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_identity(self):
        if self.project_id and not _IDENTIFIER.fullmatch(self.project_id):
            raise ValueError("项目 ID 只能包含字母、数字、下划线和连字符")
        file_ids, item_ids, indices, paths = set(), set(), set(), set()
        for key, file in self.files.items():
            validate_storage_path(key)
            if file.storage_path and file.storage_path != key:
                raise ValueError("files 键与 storage_path 不一致")
            path_key = _path_key(key)
            if path_key in paths:
                raise ValueError("模型包含指向同一输出路径的文件")
            paths.add(path_key)
            _unique_id(file.file_id, file_ids, "file_id")
            for item in file.items:
                _unique_id(item.item_id, item_ids, "item_id")
                if item.text_index in indices:
                    raise ValueError("text_index 必须在项目内唯一")
                indices.add(item.text_index)
                if item.locator and file.media_type and item.locator.kind != file.media_type:
                    raise ValueError("片段 locator.kind 与文件 media_type 不一致")
        return self


def _unique_id(value: str, seen: set, name: str) -> None:
    if not value:
        return
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} 只能包含字母、数字、下划线和连字符")
    if value in seen:
        raise ValueError(f"重复的 {name}")
    seen.add(value)


def _path_key(path: str) -> str:
    path = path.replace("\\", "/")
    return path.casefold() if os.name == "nt" else path


def validate_storage_path(path: str) -> None:
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ValueError("storage_path 必须为非空相对路径")
    parts = path.replace("\\", "/").split("/")
    if PureWindowsPath(path).drive or PurePosixPath(path).is_absolute() or any(p in ("", ".", "..") for p in parts):
        raise ValueError("storage_path 必须位于输出目录内，不能包含绝对路径或父目录")


def normalize_project(project: CacheProject) -> CacheProject:
    """Add stable identities/defaults in place; never verify or read a source file."""
    if project.schema_version not in (1, SCHEMA_VERSION):
        raise PipelineError("UNSUPPORTED_MODEL_VERSION", "不支持的中间模型版本", 422)
    project.schema_version = SCHEMA_VERSION
    if not project.project_id:
        project.project_id = uuid.uuid4().hex
    if not project.project_create_time:
        project.project_create_time = datetime.now().isoformat(timespec="seconds")
    for storage_path, file in project.files.items():
        if not file.storage_path:
            file.storage_path = storage_path
        if not file.file_id:
            file.file_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ainiee:{project.project_id}:{storage_path}").hex
        if not file.media_type:
            file.media_type = "pdf" if file.file_project_type in ("BabeldocPdf", "OfficeConversionPdf") else "document"
        if not file.source_ref and project.input_path:
            base = Path(project.input_path).expanduser()
            # Old caches saved either a directory or the single source file path.
            source = base if len(project.files) == 1 and base.name == Path(storage_path).name else base / storage_path
            file.source_ref = {"path": os.path.abspath(source), "sha256": "", "verified": False}
        for ordinal, item in enumerate(file.items):
            if not item.item_id:
                item.item_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ainiee:{file.file_id}:{item.text_index}:{ordinal}").hex
            if not item.locator:
                item.locator = {"kind": file.media_type, "index": ordinal}
    return project


def parse_model(data: dict | CacheProject | IntermediateModel) -> CacheProject:
    """Validate and copy a model; callers never mutate a desktop/global project."""
    if isinstance(data, CacheProject):
        payload = data.to_dict()
    elif isinstance(data, IntermediateModel):
        payload = data.model_dump(exclude_unset=True)
    elif isinstance(data, dict):
        payload = copy.deepcopy(data)
    else:
        raise PipelineError("INVALID_MODEL", "中间模型必须是 JSON 对象", 422)
    version = payload.get("schema_version", SCHEMA_VERSION)
    if type(version) is not int or version != SCHEMA_VERSION:
        raise PipelineError("UNSUPPORTED_MODEL_VERSION", "不支持的中间模型版本", 422)
    try:
        validated = IntermediateModel.model_validate(payload)
        clean = validated.model_dump(exclude_unset=True)
        project = CacheProject.from_dict(clean)
        normalize_project(project)
        # Validate identifiers introduced by normalization and all stored fields.
        IntermediateModel.model_validate(project.to_dict())
        return project
    except (ValidationError, ValueError, TypeError) as error:
        if isinstance(error, PipelineError):
            raise
        raise PipelineError("INVALID_MODEL", "中间模型结构无效", 422, str(error)) from error


def generate_previous_chunks(all_items: list[CacheItem], previous_item_count: int, start_idx: int) -> list[CacheItem]:
    if not all_items or previous_item_count <= 0 or start_idx <= 0:
        return []
    return all_items[max(0, start_idx - previous_item_count):min(start_idx, len(all_items))]


def generate_item_chunks(project: CacheProject, limit_type: str, limit_count: int, previous_line_count: int):
    """Existing cache batching without constructing a subscribing CacheManager."""
    if limit_type not in ("line", "token") or limit_count <= 0:
        raise ValueError("分块类型或数量无效")
    chunks, previous_chunks, file_paths = [], [], []
    for file in project.files.values():
        items = [item for item in file.items if item.translation_status == TranslationStatus.UNTRANSLATED]
        current_chunk, current_length, start_index = [], 0, 0
        for index, item in enumerate(items):
            item_length = item.get_token_count(item.source_text) if limit_type == "token" else 1
            if not current_chunk:
                start_index = index
            if current_chunk and current_length + item_length > limit_count:
                chunks.append(current_chunk)
                previous_chunks.append(generate_previous_chunks(items, previous_line_count, start_index))
                file_paths.append(file.storage_path)
                current_chunk, current_length, start_index = [], 0, index
            current_chunk.append(item)
            current_length += item_length
        if current_chunk:
            chunks.append(current_chunk)
            previous_chunks.append(generate_previous_chunks(items, previous_line_count, start_index))
            file_paths.append(file.storage_path)
    return chunks, previous_chunks, file_paths
