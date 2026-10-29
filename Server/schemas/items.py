from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ItemRecord(BaseModel):
    id: str
    file: str
    index: int
    position: int = Field(description="Zero-based position in this file, used to locate a check result.")
    source_text: str
    translated_text: str
    translation_status: int
    model: str
    flagged: bool


class ItemListResponse(BaseModel):
    project_id: str
    items: list[ItemRecord]
    total: int
    page: int
    size: int


class ItemListQuery(BaseModel):
    file: str | None = None
    status: Literal[0, 1, 2, 7, 8] | None = None
    q: Annotated[str, Field(max_length=4096)] = ""
    regex: bool = False
    flagged: bool | None = None
    page: Annotated[int, Field(ge=1)] = 1
    size: Annotated[int, Field(ge=1, le=1000)] = 100

    @field_validator("status", mode="before")
    @classmethod
    def parse_query_status(cls, value):
        # Query strings arrive as text; Literal[int] itself does not coerce it.
        return int(value) if isinstance(value, str) and value.isdecimal() else value


class ItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    source_text: Annotated[str, Field(max_length=1000000)] | None = None
    translated_text: Annotated[str, Field(max_length=1000000)] | None = None

    @model_validator(mode="after")
    def require_text(self):
        text_fields = self.model_fields_set - {"project_id"}
        if not text_fields or any(getattr(self, name) is None for name in text_fields):
            raise ValueError("Supply at least one non-null text field")
        return self
