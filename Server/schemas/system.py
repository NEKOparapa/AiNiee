from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class VersionResponse(BaseModel):
    version: str


class ShutdownResponse(BaseModel):
    status: Literal["shutting_down"]


class UpdateResponse(BaseModel):
    current_version: str
    latest_version: str
    update_available: bool
    release_url: str | None


class ErrorResponse(BaseModel):
    detail: str


class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    detail: list[ValidationIssue]
