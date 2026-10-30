from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from Server.schemas.events import TaskProgress


class AnalysisProgress(BaseModel):
    status: str = "running"
    phase: str = "prepare"
    phase_label: str = ""
    current: int = 0
    total: int = 0
    percent: int = 0
    message: str = ""
    detail: str = ""


class TaskStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    continue_task: bool = Field(default=False, alias="continue")


class TaskCurrentResponse(BaseModel):
    status: Literal["idle", "running", "stopping", "stopped", "completed", "failed", "api_test", "glossary", "analysis", "table", "unknown"]
    project_id: str | None
    project_name: str | None
    progress: TaskProgress
    mode: Literal["translate", "polish", "analysis"] | None = None
    can_continue: bool = False
    last_error: str | None = None
    analysis_progress: AnalysisProgress | None = None
