"""Platform contracts exported to the frontend through OpenAPI."""

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model
from pydantic_core import PydanticUndefined


PlatformFormat = Literal["OpenAI", "Anthropic", "Google", "Amazon Bedrock"]


class PlatformSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    name: Annotated[str, Field(min_length=1, max_length=200)]
    model: Annotated[str, Field(min_length=1, max_length=500)]
    api_url: str
    api_key: str
    api_format: PlatformFormat
    auto_complete: bool
    region: str
    access_key: str
    secret_key: str
    rpm_limit: Annotated[int, Field(strict=True, ge=0, le=9999999)]
    temperature: Annotated[float, Field(ge=0, le=2)]
    think_switch: bool
    think_depth: Literal["low", "medium", "high", "xhigh", "max"]
    thinking_budget: Annotated[int, Field(strict=True, ge=-1, le=32768)]
    thinking_level: Literal["minimal", "low", "medium", "high"]
    tls_switch: bool
    extra_body: dict[str, JsonValue]
    extra_headers: dict[str, str]
    model_datas: list[str]


def _optional_field(field):
    result = deepcopy(field)
    result.default = PydanticUndefined
    result.default_factory = lambda: None
    return result


PlatformUpdate = create_model(
    "PlatformUpdate", __base__=BaseModel, __module__=__name__,
    __config__=ConfigDict(extra="forbid", allow_inf_nan=False),
    **{name: (field.annotation, _optional_field(field)) for name, field in PlatformSettings.model_fields.items()},
)


class PlatformCreate(PlatformUpdate):
    preset_id: str
    name: Annotated[str, Field(min_length=1, max_length=200)]
    model: Annotated[str, Field(min_length=1, max_length=500)]


class PlatformMetadata(BaseModel):
    fields: list[str]
    think_depth_options: list[str]
    thinking_level_options: list[str]


class PlatformResponse(BaseModel):
    # Preserve arbitrary legacy extension values without forcing a migration.
    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)

    id: str
    tag: str
    group: str
    name: str
    model: str
    api_url: str
    api_key: str
    api_format: str
    auto_complete: bool
    region: str
    access_key: str
    secret_key: str
    rpm_limit: int
    temperature: float
    think_switch: bool
    think_depth: str
    thinking_budget: int
    thinking_level: str
    tls_switch: bool
    extra_body: dict[str, JsonValue]
    extra_headers: dict[str, str]
    model_datas: list[str]
    format_datas: list[str]
    region_datas: list[str]
    key_in_settings: list[str]
    metadata: PlatformMetadata


class PlatformBindings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: str | None
    extract: str | None
    translate: str | None
    polish: str | None
    proofread: str | None


class PlatformListResponse(BaseModel):
    platforms: list[PlatformResponse]
    presets: list[PlatformResponse]
    bindings: PlatformBindings


class PlatformDeleteResponse(BaseModel):
    deleted: Literal[True]


class PlatformModelsResponse(BaseModel):
    platform_id: str
    models: list[str]


class PlatformTestKeyResult(BaseModel):
    key_index: int
    success: bool
    error_code: str | None


class PlatformTestResponse(BaseModel):
    platform_id: str
    success_count: int
    failure_count: int
    results: list[PlatformTestKeyResult]
