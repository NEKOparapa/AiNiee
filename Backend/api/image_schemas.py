"""HTTP contracts for image model operations; provider code stays independent."""
from typing import Any, Literal

from pydantic import Field

from Backend.api.pipeline_schemas import TranslationOptions
from Backend.api.schemas import RequestModel
from Backend.domain.models.intermediate import IntermediateModel


class ImageReadOptions(RequestModel):
    exclude_rule: str = ""


class ImageReadRequest(RequestModel):
    path: str = Field(min_length=1)
    options: ImageReadOptions = Field(default_factory=ImageReadOptions)


class OcrOptions(RequestModel):
    provider_id: str | None = None
    api_url: str | None = None
    api_key: str | None = Field(default=None, repr=False)
    api_format: Literal["DashScope"] | None = None
    model: str | None = None
    request_timeout: float | None = Field(default=None, gt=0, le=3600)
    max_retries: int | None = Field(default=None, ge=0, le=5, strict=True)
    reocr: bool | None = None
    reading_order: Literal["auto", "ltr", "manga_rtl"] | None = None
    group_lines: bool | None = None
    refine_text: bool | None = None
    max_pixels: int | None = Field(default=None, ge=3136, le=23520000, strict=True)
    max_tokens: int | None = Field(default=None, ge=1, le=32768, strict=True)


class OcrRequest(RequestModel):
    model: IntermediateModel
    config: OcrOptions = Field(default_factory=OcrOptions)


class ImageWriteOptions(RequestModel):
    output_dir: str = Field(min_length=1)
    format: Literal["png", "jpeg", "webp"] = "png"
    suffix: str = "_translated"
    overwrite: bool = False
    font_path: str | None = None
    font_size: int | None = Field(default=None, ge=6, le=512, strict=True)
    min_font_size: int = Field(default=12, ge=6, le=512, strict=True)
    max_font_size: int = Field(default=48, ge=6, le=512, strict=True)
    font_color: str | None = None
    text_direction: Literal["auto", "horizontal", "vertical"] = "auto"
    padding: int = Field(default=2, ge=0, le=100, strict=True)
    erase_mode: Literal["auto", "solid", "inpaint"] = "auto"
    save_model: bool = True
    debug_overlay: bool = False


class ImageWriteRequest(RequestModel):
    model: IntermediateModel
    options: ImageWriteOptions


class ImageTranslateRequest(RequestModel):
    path: str = Field(min_length=1)
    read_options: ImageReadOptions = Field(default_factory=ImageReadOptions)
    ocr: OcrOptions = Field(default_factory=OcrOptions)
    translation: TranslationOptions = Field(default_factory=TranslationOptions)
    output: ImageWriteOptions


class ImagePipelineResponse(RequestModel):
    status: Literal["success", "partial", "failed", "cancelled"]
    model: IntermediateModel
    files: list[dict[str, Any]] = Field(default_factory=list)
    model_path: str | None = None
    report: dict[str, Any]
