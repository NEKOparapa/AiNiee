"""HTTP contracts for image model operations; provider code stays independent."""
from typing import Any, Literal

from pydantic import Field

from Backend.api.schemas import RequestModel
from Backend.domain.models.intermediate import IntermediateModel


class ImageReadOptions(RequestModel):
    exclude_rule: str = ""


class ImageReadRequest(RequestModel):
    path: str = Field(min_length=1)
    options: ImageReadOptions = Field(default_factory=ImageReadOptions)


class ImagePipelineResponse(RequestModel):
    status: Literal["success", "partial", "failed", "cancelled"]
    model: IntermediateModel
    files: list[dict[str, Any]] = Field(default_factory=list)
    model_path: str | None = None
    report: dict[str, Any]
