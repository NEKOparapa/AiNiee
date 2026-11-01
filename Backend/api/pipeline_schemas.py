"""Explicit contracts for the six intermediate-model operations."""
from typing import Any, Literal

from pydantic import Field

from Backend.api.schemas import RequestModel
from Backend.domain.models.intermediate import IntermediateModel


class DocumentReadOptions(RequestModel):
    format: str = "AutoType"
    exclude_rule: str = ""


class PdfReadOptions(RequestModel):
    exclude_rule: str = ""
    pages: str | None = None


class EmptyReadOptions(RequestModel):
    pass


class DocumentReadRequest(RequestModel):
    path: str = Field(min_length=1)
    options: DocumentReadOptions = Field(default_factory=DocumentReadOptions)


class PdfReadRequest(RequestModel):
    path: str = Field(min_length=1)
    options: PdfReadOptions = Field(default_factory=PdfReadOptions)


class MediaReadRequest(RequestModel):
    path: str = Field(min_length=1)
    options: EmptyReadOptions = Field(default_factory=EmptyReadOptions)


class TranslationOptions(RequestModel):
    """Omitted fields inherit one read-only backend configuration snapshot."""
    provider_id: str | None = None
    source_language: str | None = None
    target_language: str | None = None
    retranslate: bool | None = None
    lines_limit: int | None = Field(default=None, ge=1, le=9999999)
    tokens_limit: int | None = Field(default=None, ge=1, le=9999999)
    lines_limit_switch: bool | None = None
    tokens_limit_switch: bool | None = None
    pre_line_counts: int | None = Field(default=None, ge=0, le=9999999)
    round_limit: int | None = Field(default=None, ge=0, le=9999999)
    request_timeout: float | None = Field(default=None, gt=0, le=9999999)
    user_thread_counts: int | None = Field(default=None, ge=0, le=9999999)
    language_filter_switch: bool | None = None
    code_filter_switch: bool | None = None
    few_shot_and_example_switch: bool | None = None
    auto_process_text_code_segment: bool | None = None
    text_symbol_repair_switch: bool | None = None
    response_check_switch: dict[str, bool] | None = None
    translation_prompt_selection: dict[str, Any] | None = None
    characterization_switch: bool | None = None
    characterization_data: list[dict[str, Any]] | None = None
    translation_example_switch: bool | None = None
    translation_example_data: list[dict[str, Any]] | None = None
    world_building_switch: bool | None = None
    world_building_content: str | None = None
    writing_style_switch: bool | None = None
    writing_style_content: str | None = None
    prompt_dictionary_tables: list[dict[str, Any]] | None = None
    exclusion_list_tables: list[dict[str, Any]] | None = None
    pre_translation_tables: list[dict[str, Any]] | None = None
    post_translation_tables: list[dict[str, Any]] | None = None
    prompt_dictionary_switch: bool | None = None
    prompt_dictionary_data: list[dict[str, Any]] | None = None
    exclusion_list_switch: bool | None = None
    exclusion_list_data: list[dict[str, Any]] | None = None
    pre_translation_switch: bool | None = None
    pre_translation_data: list[dict[str, Any]] | None = None
    post_translation_switch: bool | None = None
    post_translation_data: list[dict[str, Any]] | None = None


class TranslateRequest(RequestModel):
    model: IntermediateModel
    config: TranslationOptions = Field(default_factory=TranslationOptions)


class WriteOptions(RequestModel):
    output_dir: str | None = None
    mode: Literal["translated", "bilingual", "both"] = "translated"
    translated_suffix: str = "_translated"
    bilingual_suffix: str = "_bilingual"
    bilingual_order: Literal["source_first", "translation_first"] = "source_first"
    keep_original_encoding: bool = False
    overwrite: bool = False
    source_language: str | None = None
    target_language: str | None = None


class WriteRequest(RequestModel):
    model: IntermediateModel
    options: WriteOptions = Field(default_factory=WriteOptions)


class ModelResponse(RequestModel):
    status: Literal["success", "partial", "failed", "cancelled"]
    model: IntermediateModel
    report: dict[str, Any]


class WriteResponse(RequestModel):
    status: Literal["success", "partial", "failed"]
    files: list[dict[str, Any]]
    report: dict[str, Any]
