from pydantic import BaseModel, ConfigDict, Field


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_path: str | None = Field(default=None, min_length=1, max_length=32767)


class ExportResponse(BaseModel):
    output_path: str
    files: list[str]


class CacheSaveResponse(BaseModel):
    saved: bool
