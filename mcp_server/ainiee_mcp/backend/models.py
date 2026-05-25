"""Plain serializable result types returned by any backend (transport-agnostic)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..enums import STATUS_NAMES


@dataclass
class TaskStatus:
    app_status: str = "IDLE"          # IDLE | TASKING | STOPPING | STOPPED
    work_status_code: int = 0
    has_project: bool = False
    project_id: str = ""
    project_name: str = ""
    total_line: int = 0
    line: int = 0
    remaining_line: int = 0
    percent: float = 0.0
    is_complete: bool = False
    total_requests: int = 0
    error_requests: int = 0
    token: int = 0
    total_completion_tokens: int = 0
    elapsed_seconds: int = 0
    async_tasks: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, resp: dict) -> "TaskStatus":
        p = resp.get("progress", {}) or {}
        _i = lambda v: int(v or 0)
        return cls(
            app_status=resp.get("app_status", "IDLE"),
            work_status_code=_i(resp.get("work_status_code")),
            has_project=bool(resp.get("has_project", False)),
            project_id=resp.get("project_id", "") or "",
            project_name=resp.get("project_name", "") or "",
            total_line=_i(p.get("total_line")),
            line=_i(p.get("line")),
            remaining_line=_i(p.get("remaining_line")),
            percent=float(p.get("percent", 0.0) or 0.0),
            is_complete=bool(p.get("is_complete", False)),
            total_requests=_i(p.get("total_requests")),
            error_requests=_i(p.get("error_requests")),
            token=_i(p.get("token")),
            total_completion_tokens=_i(p.get("total_completion_tokens")),
            elapsed_seconds=_i(p.get("elapsed_seconds")),
            async_tasks=resp.get("async", {}) or {},
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnalysisResult:
    status: str = ""
    characters: list = field(default_factory=list)
    terms: list = field(default_factory=list)
    non_translate: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    message: str = ""
    last_run_at: str = ""

    @classmethod
    def from_payload(cls, payload: dict) -> "AnalysisResult":
        data = payload.get("analysis_data") or {}
        return cls(
            status=payload.get("status", "") or "",
            characters=data.get("characters", []) or [],
            terms=data.get("terms", []) or [],
            non_translate=data.get("non_translate", []) or [],
            stats=data.get("stats", {}) or {},
            message=payload.get("message", "") or "",
            last_run_at=data.get("last_run_at", "") or "",
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GlossaryResult:
    status: str = ""
    updated_data: list = field(default_factory=list)
    success_count: int = 0
    total_count: int = 0
    message: str = ""

    @classmethod
    def from_payload(cls, payload: dict) -> "GlossaryResult":
        return cls(
            status=payload.get("status", "") or "",
            updated_data=payload.get("updated_data") or [],
            success_count=int(payload.get("success_count", 0) or 0),
            total_count=int(payload.get("total_count", 0) or 0),
            message=payload.get("message", "") or "",
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ApiTestResult:
    success: list = field(default_factory=list)
    failure: list = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict) -> "ApiTestResult":
        return cls(
            success=payload.get("success") or [],
            failure=payload.get("failure") or [],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CacheItemView:
    storage_path: str
    text_index: int
    source_text: str
    translated_text: str
    status: int
    status_name: str = ""

    def __post_init__(self):
        if not self.status_name:
            self.status_name = STATUS_NAMES.get(self.status, str(self.status))

    @classmethod
    def from_dict(cls, d: dict) -> "CacheItemView":
        status = int(d.get("status", 0) or 0)
        return cls(
            storage_path=d.get("storage_path", "") or "",
            text_index=int(d.get("text_index", 0) or 0),
            source_text=d.get("source_text", "") or "",
            translated_text=d.get("translated_text", "") or "",
            status=status,
            status_name=d.get("status_name") or STATUS_NAMES.get(status, str(status)),
        )

    def to_dict(self) -> dict:
        return asdict(self)
