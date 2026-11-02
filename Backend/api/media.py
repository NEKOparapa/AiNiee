"""Media import, persistence, and authenticated preview assets."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import Field

from Backend.api.schemas import RequestModel
from Backend.application.execution_context import ExecutionContext
from Backend.application.media_workspace_service import get_media_store
from Backend.domain.models.intermediate import IntermediateModel


class MediaImportRequest(RequestModel):
    kind: Literal["image", "audio"]
    paths: list[str] = Field(min_length=1, max_length=100)
    exclude_rule: str = ""


class MediaSaveRequest(RequestModel):
    model: IntermediateModel
    preview_files: list[dict[str, Any]] | None = None


def create_media_router(runtime, authorized):
    router = APIRouter(prefix="/api/v2/media", tags=["Media workspaces"], dependencies=[Depends(authorized)])
    store = get_media_store(runtime)

    @router.post("/import")
    def import_media(body: MediaImportRequest):
        with runtime.operation("media/import", context=ExecutionContext()):
            return store.import_media(body.kind, body.paths, body.exclude_rule)

    @router.get("")
    def history(kind: Literal["image", "audio"] | None = None, limit: int = Query(default=20, ge=1, le=100)):
        return {"workspaces": store.history(kind, limit)}

    @router.get("/{workspace_id}")
    def load(workspace_id: str):
        return store.load(workspace_id)

    @router.post("/{workspace_id}/model")
    def save(workspace_id: str, body: MediaSaveRequest):
        # Public saves share admission with runs, imports, and deletion.
        # Internal paid-stage checkpoints call the store directly.
        with runtime.operation(f"media/{workspace_id}/save", context=ExecutionContext()):
            return store.save_model(workspace_id, body.model.model_dump(), preview_files=body.preview_files)

    @router.delete("/{workspace_id}")
    def delete(workspace_id: str):
        with runtime.operation(f"media/{workspace_id}/delete", context=ExecutionContext()):
            return store.delete(workspace_id)

    @router.get("/{workspace_id}/files/{file_id}/{variant}")
    @router.head("/{workspace_id}/files/{file_id}/{variant}")
    def preview(workspace_id: str, file_id: str, variant: Literal["source", "translated"]):
        path = store.asset(workspace_id, file_id, variant)
        # Starlette's FileResponse handles byte ranges and HEAD for QMediaPlayer.
        return FileResponse(path, filename=path.name, content_disposition_type="inline", headers={"Cache-Control": "no-cache"})

    return router
