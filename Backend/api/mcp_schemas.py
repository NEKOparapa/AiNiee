"""MCP submissions reuse the public pipeline contracts and queue identifiers."""
from typing import Literal

from pydantic import Field

from Backend.api.audio_schemas import AudioTranslateRequest
from Backend.api.image_generation import GenerationPipelineRequest
from Backend.api.pipeline_schemas import DocumentReadOptions, TranslationOptions, WriteOptions
from Backend.api.schemas import RequestModel


class MCPRequestId(RequestModel):
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,80}$")


class DocumentTranslationRequest(MCPRequestId):
    path: str = Field(min_length=1)
    read_options: DocumentReadOptions = Field(default_factory=DocumentReadOptions)
    translation: TranslationOptions = Field(default_factory=TranslationOptions)
    output: WriteOptions | None = None


class MCPImageGenerationRequest(GenerationPipelineRequest, MCPRequestId):
    # MCP has one idempotency identifier. The REST-specific alias is not used.
    operation_id: None = Field(default=None, exclude=True)


class MCPAudioTranslationRequest(AudioTranslateRequest, MCPRequestId):
    pass


class MCPJobQuery(RequestModel):
    job_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    include_result: bool = Field(default=False, strict=True)


class MCPJobListQuery(RequestModel):
    lane: Literal["document", "image", "audio"] | None = None
    limit: int = Field(default=50, ge=1, le=200, strict=True)
