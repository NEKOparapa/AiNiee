"""Named workspace operations; no event identifiers cross the API boundary."""
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from Backend.api.schemas import RequestModel


class TranslationStart(RequestModel):
    continue_status: bool = False


class ExportRequest(RequestModel):
    export_path: str | None = None


class TableItem(RequestModel):
    text_index: int = Field(ge=0)
    source_text: str
    translation_text: str = ""
    error_type: str = ""


class TranslateJob(RequestModel):
    file_path: str = Field(min_length=1)
    items_to_translate: list[TableItem]
    language_stats: list[tuple[str, int, float]] | None = None


class PolishJob(RequestModel):
    file_path: str = Field(min_length=1)
    items_to_polish: list[TableItem]


class ProofreadJob(RequestModel):
    file_path: str = Field(min_length=1)
    items_to_proofread: list[TableItem]


class TableRequest(RequestModel):
    view: Literal["basic", "search", "language_check", "rule_check", "terminology_check"] = "basic"
    file_path: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_one_input_form(self):
        fields = type(self).model_fields
        items_key = next(name for name in fields if name.startswith("items_to_"))
        jobs_key = next(name for name in fields if name.endswith("_jobs"))
        items, jobs = getattr(self, items_key), getattr(self, jobs_key)
        if jobs is not None:
            if self.file_path is not None or items is not None:
                raise ValueError("不能同时提供单文件参数和多文件 jobs")
        elif self.file_path is None or items is None:
            raise ValueError("请提供 file_path 和条目列表，或多文件 jobs")
        return self


class TableTranslateRequest(TableRequest):
    items_to_translate: list[TableItem] | None = None
    language_stats: list[tuple[str, int, float]] | None = None
    translate_jobs: list[TranslateJob] | None = None


class TablePolishRequest(TableRequest):
    items_to_polish: list[TableItem] | None = None
    polish_jobs: list[PolishJob] | None = None


class TableProofreadRequest(TableRequest):
    items_to_proofread: list[TableItem] | None = None
    proofread_jobs: list[ProofreadJob] | None = None


class GlossaryRequest(RequestModel):
    table_id: str | None = None
    request_id: str | None = None
    prompt_dictionary_data: list[dict[str, Any]] = Field(default_factory=list)


class ApiTestRequest(RequestModel):
    # Providers attach extra options to their saved configuration. Preserve
    # those options while validating the common fields used by this operation.
    model_config = ConfigDict(extra="allow")
    tag: str = ""
    name: str = ""
    api_url: str = ""
    api_key: str = ""
    api_format: str = ""
    model: str = ""
    auto_complete: bool = True
    extra_body: dict[str, Any] = Field(default_factory=dict)
    extra_headers: dict[str, str] = Field(default_factory=dict)
