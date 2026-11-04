"""Media import, persistence, and authenticated preview assets."""
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from pydantic import Field

from Backend.api.schemas import RequestModel
from Backend.api.queued import load_media_workspace, media_lane, run_queued
from Backend.application.pipeline_common import PipelineError
from Backend.application.media_workspace_service import get_media_store
from Backend.domain.models.intermediate import IntermediateModel


class MediaImportRequest(RequestModel):
    kind: Literal["image", "audio", "video"]
    paths: list[str] = Field(min_length=1, max_length=100, description="媒体文件或目录路径，不读取压缩包")
    exclude_rule: str = ""
    operation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,80}$")


class MediaSaveRequest(RequestModel):
    model: IntermediateModel


class VideoPreviewRequest(RequestModel):
    operation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,80}$")


def create_media_router(runtime, authorized):
    router = APIRouter(prefix="/api/v2/media", tags=["Media workspaces"], dependencies=[Depends(authorized)])
    store = get_media_store(runtime)

    @router.post("/import")
    async def import_media(body: MediaImportRequest, prefer: str | None = Header(default=None)):
        return await run_queued(runtime, "media/import", lambda context: store.import_media(
            body.kind, body.paths, body.exclude_rule, context=context), lane=body.kind, prefer=prefer,
            operation_id=body.operation_id)

    @router.get("")
    def history(kind: Literal["image", "audio", "video"] | None = None, limit: int = Query(default=20, ge=1, le=100)):
        return {"workspaces": store.history(kind, limit)}

    @router.get("/{workspace_id}")
    def load(workspace_id: str):
        return store.load(workspace_id)

    @router.post("/{workspace_id}/model")
    async def save(workspace_id: str, body: MediaSaveRequest, prefer: str | None = Header(default=None)):
        # Public saves share admission with runs, imports, and deletion.
        # Internal paid-stage checkpoints call the store directly.
        workspace = await run_in_threadpool(load_media_workspace, store, workspace_id)
        lane, revision = workspace["kind"], workspace["updated_at"]
        def action(context):
            current = load_media_workspace(store, workspace_id)
            if current["updated_at"] != revision:
                raise PipelineError("MEDIA_WORKSPACE_CHANGED", "项目在等待保存期间已更新，请刷新后重新保存", 409)
            return store.save_model(workspace_id, body.model.model_dump())
        return await run_queued(runtime, f"media/{workspace_id}/save", action, lane=lane,
                          prefer=prefer, project_id=workspace_id)

    @router.delete("/{workspace_id}")
    async def delete(workspace_id: str, prefer: str | None = Header(default=None)):
        lane = await run_in_threadpool(media_lane, store, workspace_id)
        def action(context):
            store.load(workspace_id)
            return store.delete(workspace_id)
        return await run_queued(runtime, f"media/{workspace_id}/delete", action, lane=lane,
                          prefer=prefer, project_id=workspace_id)

    @router.post("/{workspace_id}/files/{file_id}/video-preview")
    async def video_preview(workspace_id: str, file_id: str, body: VideoPreviewRequest,
                            prefer: str | None = Header(default=None)):
        lane = await run_in_threadpool(media_lane, store, workspace_id)
        return await run_queued(runtime, f"media/{workspace_id}/video-preview",
                                lambda context: store.prepare_video_preview(workspace_id, file_id, context),
                                lane=lane, prefer=prefer, project_id=workspace_id, operation_id=body.operation_id)

    @router.get("/{workspace_id}/files/{file_id}/{variant}")
    @router.head("/{workspace_id}/files/{file_id}/{variant}")
    def preview(workspace_id: str, file_id: str, variant: Literal["source", "translated", "preview"]):
        path = store.asset(workspace_id, file_id, variant)
        # Starlette's FileResponse handles byte ranges and HEAD for QMediaPlayer.
        return FileResponse(path, filename=path.name, content_disposition_type="inline", headers={"Cache-Control": "no-cache"})

    return router
