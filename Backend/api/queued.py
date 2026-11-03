"""Shared HTTP response handling for queued application operations."""
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.protocol import to_wire


def wants_async(prefer):
    return any(value.split(";", 1)[0].strip().lower() == "respond-async"
               for value in (prefer or "").split(","))


async def run_queued(runtime, name, action, *, lane, prefer=None, context=None,
                     operation_id=None, project_id=None):
    background = wants_async(prefer)
    context = context or ExecutionContext(on_progress=runtime.pipeline_progress)
    result = await run_in_threadpool(
        runtime.run_job, name, action, lane=lane, source="api", context=context,
        operation_id=operation_id, project_id=project_id, background=True,
    )
    if background:
        headers = {"Preference-Applied": "respond-async"}
        identifier = result.get("job_id") or result.get("id")
        if identifier:
            headers["Location"] = f"/api/jobs/{identifier}"
        return JSONResponse(status_code=202, content={"job": to_wire(result)}, headers=headers)
    return to_wire(await runtime.scheduler.wait(result.get("job_id") or result["id"]))


def media_lane(store, workspace_id):
    """Only the persisted workspace kind determines its execution queue."""
    return load_media_workspace(store, workspace_id)["kind"]


def load_media_workspace(store, workspace_id):
    workspace = store.load(workspace_id)
    kind = workspace["kind"]
    if kind not in ("image", "audio", "video"):
        raise PipelineError("INVALID_MEDIA_KIND", "媒体项目类型无效", 422)
    return workspace


def require_model_lane(runtime, model, expected):
    lane = runtime.lane_for_model(model)
    allowed = (expected,) if isinstance(expected, str) else expected
    if lane not in allowed:
        raise PipelineError("INVALID_PROJECT_KIND", f"此接口仅接受 {expected} 项目", 422)
    return lane
