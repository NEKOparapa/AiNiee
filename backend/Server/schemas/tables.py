"""Public-table contracts; unknown row metadata survives round trips."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from Server.schemas.config import JsonObjectModel

TableName = Literal["glossary", "exclusion", "replace_a", "replace_b", "characters"]


class TableRow(JsonObjectModel):
    src: str = ""
    dst: str = ""
    info: str = ""
    markers: str = ""
    regex: bool = False
    original_name: str = ""
    translated_name: str = ""
    gender: str = ""
    age: str = ""
    personality: str = ""
    speech_style: str = ""
    additional_info: str = ""


class TableMatchOptions(JsonObjectModel):
    case_sensitive: bool = False
    whole_word: bool = False
    split_match: bool = False


class PublicTable(JsonObjectModel):
    id: Annotated[str, Field(min_length=1, max_length=200)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    enabled: bool = True
    rows: list[TableRow] = Field(default_factory=list)
    match_options: TableMatchOptions | None = None


class TableCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tables: list[PublicTable]
    active_table_id: str | None = None


class TableImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: Annotated[str, Field(min_length=1, max_length=500)]
    content_base64: Annotated[str, Field(max_length=28000000)]
    mode: Literal["new", "merge"] = "new"
    target_table_id: str | None = None
    selected_table_ids: list[str] | None = None
    preview: bool = False


class TableDownload(BaseModel):
    filename: str
    media_type: str
    content_base64: str
