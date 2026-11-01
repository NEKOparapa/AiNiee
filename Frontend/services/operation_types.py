"""Desktop request shapes for the explicit task endpoints."""
from typing import Any, Literal, NotRequired, TypedDict


TableView = Literal["basic", "search", "language_check", "rule_check", "terminology_check"]


class TableItem(TypedDict):
    text_index: int
    source_text: str
    translation_text: NotRequired[str]
    error_type: NotRequired[str]


class TranslateJob(TypedDict):
    file_path: str
    items_to_translate: list[TableItem]
    language_stats: NotRequired[list[Any] | None]


class PolishJob(TypedDict):
    file_path: str
    items_to_polish: list[TableItem]


class ProofreadJob(TypedDict):
    file_path: str
    items_to_proofread: list[TableItem]


class TableTranslateRequest(TypedDict):
    view: TableView
    file_path: NotRequired[str]
    items_to_translate: NotRequired[list[TableItem]]
    language_stats: NotRequired[list[Any] | None]
    translate_jobs: NotRequired[list[TranslateJob]]


class TablePolishRequest(TypedDict):
    view: TableView
    file_path: NotRequired[str]
    items_to_polish: NotRequired[list[TableItem]]
    polish_jobs: NotRequired[list[PolishJob]]


class TableProofreadRequest(TypedDict):
    view: TableView
    file_path: NotRequired[str]
    items_to_proofread: NotRequired[list[TableItem]]
    proofread_jobs: NotRequired[list[ProofreadJob]]


class GlossaryTranslateRequest(TypedDict):
    table_id: str
    request_id: str
    prompt_dictionary_data: list[dict[str, Any]]


# Provider configuration fields vary by API format and include custom headers.
ApiTestRequest = dict[str, Any]
