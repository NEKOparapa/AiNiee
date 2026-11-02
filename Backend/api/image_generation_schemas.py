"""Public model-in/model-out image-generation contracts."""
from typing import Literal
from pydantic import Field
from Backend.api.schemas import RequestModel
from Backend.domain.models.intermediate import IntermediateModel


class ImageTextReplacement(RequestModel):
    file_id: str = Field(min_length=1)
    source_text: str = Field(min_length=1, max_length=10000)
    target_text: str = Field(min_length=1, max_length=10000)
    location: str | None = Field(default=None, max_length=2000)


class ImageGenerationOptions(RequestModel):
    provider_id: str | None = None
    api_url: str | None = None
    api_key: str | None = Field(default=None, repr=False)
    api_format: Literal["DashScope", "VolcengineArk"] | None = None
    model: str | None = None
    request_timeout: float | None = Field(default=None, gt=0, le=3600)
    prompt_extend: bool | None = None
    watermark: bool | None = None
    size: str | None = None
    seed: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    source_language: str | None = None
    target_language: str | None = None
    prompt: str | None = Field(default=None, max_length=10000)
    text_mode: Literal["direct", "specified"] | None = None
    replacements: list[ImageTextReplacement] | None = Field(default=None, max_length=1000)
    regenerate: bool | None = None


class ImageGenerationRequest(RequestModel):
    model: IntermediateModel
    config: ImageGenerationOptions = Field(default_factory=ImageGenerationOptions)


class GeneratedImageWriteOptions(RequestModel):
    output_dir: str = Field(min_length=1)
    format: Literal["png", "jpeg", "webp"] = "png"
    suffix: str = "_translated"
    overwrite: bool = False
    save_model: bool = True


class GeneratedImageWriteRequest(RequestModel):
    model: IntermediateModel
    options: GeneratedImageWriteOptions
