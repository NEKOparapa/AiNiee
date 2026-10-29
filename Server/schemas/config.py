"""Typed settings contracts; unknown legacy/extension keys remain JSON values."""

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model
from pydantic_core import PydanticUndefined


SettingInteger = Annotated[int, Field(strict=True, ge=0, le=9999999)]
PositiveSettingInteger = Annotated[int, Field(strict=True, ge=1, le=9999999)]
Theme = Literal["auto", "light", "dark"]
OpenCCPreset = Literal[
    "s2t", "s2tw", "s2hk", "s2twp", "t2s", "t2tw", "t2hk", "t2jp",
    "tw2s", "tw2t", "tw2sp", "hk2s", "hk2t", "jp2t",
]


class JsonObjectModel(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)


class ResponseCheckSettings(JsonObjectModel):
    return_to_original_text_check: bool
    residual_original_text_check: bool
    newline_character_count_check: bool
    reply_format_check: bool


class ConfigDocument(JsonObjectModel):
    """Effective settings view, with defaults filled by ConfigService."""

    translation_project: str
    lines_limit_switch: bool
    tokens_limit_switch: bool
    lines_limit: SettingInteger
    tokens_limit: SettingInteger
    user_thread_counts: SettingInteger
    request_timeout: SettingInteger
    round_limit: SettingInteger
    label_output_path: str
    label_polish_output_path: str
    auto_set_output_path: bool
    output_filename_suffix: str
    bilingual_text_order: Literal["source_first", "translation_first", "original_first"]
    translation_result_check_switch: bool
    response_conversion_toggle: bool
    opencc_preset: OpenCCPreset
    keep_original_encoding: bool
    extract_task_token_limit: PositiveSettingInteger
    auto_extract_non_translate_switch: bool
    extract_short_name_merge_switch: bool
    source_language: str
    target_language: str
    language_filter_switch: bool
    code_filter_switch: bool
    pre_line_counts: SettingInteger
    few_shot_and_example_switch: bool
    auto_process_text_code_segment: bool
    text_symbol_repair_switch: bool
    response_check_switch: ResponseCheckSettings
    polishing_pre_line_counts: SettingInteger
    theme: Theme
    accent_color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
    interface_language_setting: str
    label_input_path: str | None = None


def _optional_field(field):
    # A factory makes the field omittable without a nullable wire type/default.
    # Exclude-unset serialization never includes these internal placeholders.
    result = deepcopy(field)
    result.default = PydanticUndefined
    result.default_factory = lambda: None
    return result


ConfigPatch = create_model(
    "ConfigPatch",
    __base__=JsonObjectModel,
    __module__=__name__,
    __doc__="Provided top-level keys replace their values; omitted keys are preserved.",
    **{
        name: (field.annotation, _optional_field(field))
        for name, field in ConfigDocument.model_fields.items()
    },
)
