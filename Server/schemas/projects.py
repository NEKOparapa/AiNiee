"""Project contracts are exported with OpenAPI for the web client."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from Server.schemas.events import TaskProgress


class ProjectOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Annotated[str, Field(min_length=1, max_length=32768)]


class ProjectSummary(BaseModel):
    project_id: str
    project_name: str
    project_type: str
    project_create_time: str
    input_path: str
    file_count: int
    item_count: int


class ProjectCurrentResponse(BaseModel):
    project: ProjectSummary | None
    supported_project_types: list[str]
    selected_project_type: str
    configured_path: str


class ProjectHistoryEntry(BaseModel):
    project_id: str
    project_name: str
    project_create_time: str
    total_line: int
    line: int
    is_complete: bool
    cache_path: str


class ProjectHistoryDeleteResponse(BaseModel):
    deleted: bool


class ProjectLanguageStat(BaseModel):
    language: str
    count: int
    confidence: float


class ProjectFile(BaseModel):
    path: str
    project_type: str
    encoding: str
    item_count: int
    translated_count: int
    polished_count: int
    excluded_count: int
    questionable_count: int
    language_stats: list[ProjectLanguageStat]


class ProjectStats(BaseModel):
    total: int
    untranslated: int
    translated: int
    polished: int
    excluded: int
    questionable: int
    other: int
    progress: TaskProgress


class FileSystemListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Annotated[str, Field(max_length=32768)] = ""


class FileSystemEntry(BaseModel):
    name: str
    path: str
    is_directory: bool


class FileSystemListResponse(BaseModel):
    path: str
    parent: str | None
    roots: list[str]
    entries: list[FileSystemEntry]
