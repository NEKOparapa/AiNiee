"""Public model-in/model-out image-generation contracts."""
from typing import Literal
from pydantic import Field
from Backend.api.schemas import RequestModel
from Backend.domain.models.intermediate import IntermediateModel


class ImageGenerationOptions(RequestModel):
    provider_id: str | None = None
    api_url: str | None = None
    api_key: str | None = Field(default=None, repr=False)
    api_format: Literal["DashScope", "VolcengineArk", "Gemini", "OpenAI"] | None = None
    model: str | None = None
    user_thread_counts: int | None = Field(default=None, ge=1, le=64, strict=True)
    request_timeout: float | None = Field(default=None, gt=0, le=3600)
    prompt_extend: bool | None = Field(default=None, description="兼容旧请求；百炼图像接口始终启用提示词自动改写，此值不影响请求。")
    watermark: bool | None = None
    size: str | None = None
    seed: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    source_language: str | None = None
    target_language: str | None = None
    prompt: str | None = Field(default=None, max_length=10000)
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
