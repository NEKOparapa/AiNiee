from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.ProjectService import ProjectService
from Server.deps import get_project_service, require_http_token
from Server.schemas.projects import (
    FileSystemListRequest,
    FileSystemListResponse,
    ProjectCurrentResponse,
    ProjectFile,
    ProjectHistoryDeleteResponse,
    ProjectHistoryEntry,
    ProjectOpenRequest,
    ProjectStats,
    ProjectSummary,
)
from Server.schemas.system import ErrorResponse


router = APIRouter(
    tags=["projects"], dependencies=[Depends(require_http_token)],
    responses={status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 409, 500)},
)
Service = Annotated[ProjectService, Depends(get_project_service)]


@router.post("/projects/open", response_model=ProjectSummary, operation_id="open_project")
def open_project(body: ProjectOpenRequest, service: Service):
    return service.open_project(body.path)


@router.get("/projects/current", response_model=ProjectCurrentResponse, operation_id="get_current_project")
def get_current_project(service: Service):
    return service.get_current()


@router.get("/projects/history", response_model=list[ProjectHistoryEntry], operation_id="get_project_history")
def get_project_history(service: Service):
    return service.get_history()


@router.delete("/projects/history/{project_id}", response_model=ProjectHistoryDeleteResponse, operation_id="delete_project_history")
def delete_project_history(project_id: str, service: Service):
    return service.delete_history(project_id)


@router.get("/projects/current/files", response_model=list[ProjectFile], operation_id="get_project_files")
def get_project_files(service: Service):
    return service.get_files()


@router.get("/projects/current/stats", response_model=ProjectStats, response_model_exclude_unset=True, operation_id="get_project_stats")
def get_project_stats(service: Service):
    return service.get_stats()


@router.post("/fs/list", response_model=FileSystemListResponse, operation_id="list_directory")
def list_directory(body: FileSystemListRequest, service: Service):
    return service.list_directory(body.path)
