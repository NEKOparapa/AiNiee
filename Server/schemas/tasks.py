from typing import Literal

from pydantic import BaseModel

from Server.schemas.events import TaskProgress


class TaskCurrentResponse(BaseModel):
    status: Literal["idle", "running", "stopping", "stopped", "api_test", "glossary", "analysis", "table", "unknown"]
    project_id: str | None
    project_name: str | None
    progress: TaskProgress
