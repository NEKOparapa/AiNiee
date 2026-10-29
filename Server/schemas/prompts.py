"""Prompt documents and the legacy per-task prompt libraries."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from Server.schemas.tables import TableRow
from Server.schemas.config import JsonObjectModel

LibraryKind = Literal["system", "polish", "analysis_basic", "analysis_judgment"]
PromptKind = Literal["system", "polish", "analysis_basic", "analysis_judgment", "world", "style", "examples", "characters"]


class PromptDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    content: str = ""
    selected_id: str | int | None = None
    rows: list[TableRow] = Field(default_factory=list)


class LibraryPrompt(JsonObjectModel):
    id: str | int
    name: str
    content: str
    type: Literal["system", "user"]
    summary: str = ""


class PromptLibrary(BaseModel):
    presets: list[LibraryPrompt]
    custom: list[LibraryPrompt]
    selected_id: str | int


class PromptUpsertRequest(JsonObjectModel):
    id: str | None = None
    name: Annotated[str, Field(min_length=1, max_length=200)]
    content: Annotated[str, Field(min_length=1)]
    select: bool = True
