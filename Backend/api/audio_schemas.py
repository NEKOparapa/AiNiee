"""Explicit contracts for audio ingestion, transcription and subtitle export."""
from typing import Any, Literal

from pydantic import Field

from Backend.api.pipeline_schemas import TranslationOptions
from Backend.api.schemas import RequestModel
from Backend.domain.models.intermediate import IntermediateModel


class AudioReadOptions(RequestModel):
    exclude_rule: str = ""


class AudioReadRequest(RequestModel):
    path: str = Field(min_length=1)
    options: AudioReadOptions = Field(default_factory=AudioReadOptions)


class TranscriptionOptions(RequestModel):
    provider_id: str | None = None
    api_url: str | None = None
    api_key: str | None = Field(default=None, repr=False)
    api_format: Literal["DashScope", "VolcengineASRFast"] | None = None
    app_id: str | None = None
    resource_id: str | None = None
    model: str | None = None
    request_timeout: float | None = Field(default=None, gt=0, le=3600)
    timeout: float | None = Field(default=None, gt=0, le=3600)
    language_hints: list[str] | None = Field(default=None, max_length=4)
    speaker_diarization_enabled: bool | None = None
    keep_dialect: bool | None = None
    stream: bool | None = None
    max_retries: int | None = Field(default=None, ge=0, le=5)
    retranscribe: bool | None = None
    chunk_duration_seconds: int | None = Field(default=None, ge=30, le=290, strict=True)
    chunk_overlap_seconds: float | None = Field(default=None, ge=0.5, le=5)
    user_thread_counts: int | None = Field(default=None, ge=1, le=64, strict=True)
    chunk_concurrency: int | None = Field(default=None, ge=1, le=8, strict=True, deprecated=True,
                                         description="兼容旧请求，作为 user_thread_counts 的别名。")
    vad_threshold: float | None = Field(default=None, ge=0.01, le=0.99)


class TranscribeRequest(RequestModel):
    model: IntermediateModel
    config: TranscriptionOptions = Field(default_factory=TranscriptionOptions)


class SubtitleOptions(RequestModel):
    output_dir: str = Field(min_length=1)
    format: Literal["srt", "vtt", "lrc", "ass"] = "srt"
    mode: Literal["translated", "source", "bilingual"] = "translated"
    bilingual_order: Literal["source_first", "translation_first"] = "source_first"
    suffix: str = "_subtitles"
    overwrite: bool = False


class SubtitleWriteRequest(RequestModel):
    model: IntermediateModel
    options: SubtitleOptions


class AudioTranslateRequest(RequestModel):
    path: str = Field(min_length=1)
    read_options: AudioReadOptions = Field(default_factory=AudioReadOptions)
    transcription: TranscriptionOptions = Field(default_factory=TranscriptionOptions)
    translation: TranslationOptions = Field(default_factory=TranslationOptions)
    output: SubtitleOptions


class AudioTranslateResponse(RequestModel):
    status: Literal["success", "partial", "failed", "cancelled"]
    model: IntermediateModel
    files: list[dict[str, Any]] = Field(default_factory=list)
    report: dict[str, Any]
