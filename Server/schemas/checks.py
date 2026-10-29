from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class RuleOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exclusion: bool = True
    auto_process: bool = True
    placeholder: bool = True
    number: bool = True
    example: bool = True
    newline: bool = True
    untranslated: bool = True


class RuleCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: RuleOptions | None = None


class LanguageCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["judge", "report"] | None = None
    chunk_size: Annotated[int, Field(ge=1, le=9999999)] | None = None
    threshold: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] | None = None
    exclude_non_translate: bool | None = None


class TerminologyCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_sensitive: bool | None = None
    whole_word: bool | None = None


class CheckIssue(BaseModel):
    id: str
    file: str
    index: int
    position: int
    error: str
    source: str
    translation: str


class LanguageReport(BaseModel):
    file: str
    project_type: str
    encoding: str
    stats: str


class CheckResponse(BaseModel):
    kind: Literal["rule", "language", "terminology"]
    project_id: str
    passed: bool
    issues: list[CheckIssue]
    reports: list[LanguageReport]
    target_language: str | None = None
    mode: Literal["judge", "report"] | None = None
