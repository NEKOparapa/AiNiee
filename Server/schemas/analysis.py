"""Typed analysis tables with extensible legacy metadata."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from Server.schemas.tables import TableCollection


AnalysisView = Literal["characters", "terms", "non_translate"]


class AnalysisRow(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    occurrence_count: Annotated[int, Field(ge=1)] = 1
    note: str = ""


class AnalysisCharacter(AnalysisRow):
    source: str = ""
    recommended_translation: str = ""
    gender: str = "其他"


class AnalysisTerm(AnalysisRow):
    source: str = ""
    recommended_translation: str = ""
    category_path: str = "Other"


class AnalysisExclusion(AnalysisRow):
    marker: str = ""
    category: str = "Other"


class AnalysisDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    project_id: Annotated[str, Field(min_length=1, max_length=256)]
    characters: list[AnalysisCharacter]
    terms: list[AnalysisTerm]
    non_translate: list[AnalysisExclusion]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class AnalysisImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: Annotated[str, Field(min_length=1, max_length=256)]
    content_base64: Annotated[str, Field(max_length=28000000)]


class AnalysisImportResponse(BaseModel):
    document: AnalysisDocument
    added: int
    replaced: int
    skipped: int


class AnalysisPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: Annotated[str, Field(min_length=1, max_length=256)]
    table_id: str | None = None
    identities: list[str] | None = Field(default=None, description="Source/marker identities to publish; omit for the entire view.")


class AnalysisPublishResponse(BaseModel):
    collection: TableCollection
    added: int


class AnalysisMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: Annotated[str, Field(min_length=1, max_length=256)]
    target: Literal["characters", "terms"]
    category: Annotated[str, Field(max_length=1000)] = ""
    identities: list[str]
