from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.ExportService import ExportService
from Server.deps import get_export_service, require_http_token
from Server.schemas.export import CacheSaveResponse, ExportRequest, ExportResponse
from Server.schemas.system import ErrorResponse


router = APIRouter(
    tags=["export"], dependencies=[Depends(require_http_token)],
    responses={status: {"model": ErrorResponse} for status in (400, 401, 403, 409, 500)},
)
Service = Annotated[ExportService, Depends(get_export_service)]


@router.post("/export", response_model=ExportResponse, operation_id="export_project")
def export_project(body: ExportRequest, service: Service):
    return service.export(body.output_path)


@router.post("/cache/save", response_model=CacheSaveResponse, operation_id="save_project_cache")
def save_project_cache(service: Service):
    return service.save_cache()
