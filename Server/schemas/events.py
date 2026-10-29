"""Backend-owned WebSocket contracts exported with the REST OpenAPI schema."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel, TypeAdapter


class EventMessage(BaseModel):
    seq: int = Field(ge=1)
    type: str
    ts: float
    data: dict[str, JsonValue]


class TaskProgress(BaseModel):
    """Existing CacheProjectStatistics fields; partial progress updates are valid."""

    model_config = ConfigDict(extra="allow")

    total_requests: int | None = None
    error_requests: int | None = None
    start_time: float | None = None
    total_line: int | None = None
    line: int | None = None
    token: int | None = None
    total_completion_tokens: int | None = None
    time: float | None = None


class TaskUpdateMessage(BaseModel):
    seq: int = Field(ge=1)
    type: Literal["task.update"]
    ts: float
    data: TaskProgress


class LogEntry(BaseModel):
    ts: float
    level: str
    logger: str
    message: str


class LogBatch(BaseModel):
    entries: list[LogEntry]


class LogMessage(BaseModel):
    seq: int = Field(ge=1)
    type: Literal["log"]
    ts: float
    data: LogBatch


WsMessage = TaskUpdateMessage | LogMessage | EventMessage
WS_MESSAGE_ADAPTER = TypeAdapter(WsMessage)


class WebSocketMessage(RootModel[WsMessage]):
    """Schema-only root used to expose WS messages in generated OpenAPI clients."""
