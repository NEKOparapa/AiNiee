"""Validated HTTP request payloads."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigPatch(RequestModel):
    values: dict[str, Any]
    table_update: bool = False
    revision: str | None = None


class ProjectLoad(RequestModel):
    project_type: str = "AutoType"
    input_path: str = Field(min_length=1)
    exclude_rule: str = ""


class CacheCall(RequestModel):
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None


class Command(RequestModel):
    event: int
    data: dict[str, Any] = Field(default_factory=dict)


class ModelQuery(RequestModel):
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    google_config: dict[str, Any] | None = None


class FolderQuery(RequestModel):
    path: str = Field(min_length=1)


class EditorCall(RequestModel):
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
