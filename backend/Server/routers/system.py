from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.SystemService import SystemService
from ModuleFolders.Application.UpdateService import UpdateService
from Server.deps import get_system_service, get_update_service, require_http_token
from Server.schemas.system import ErrorResponse, HealthResponse, ShutdownResponse, UpdateResponse, VersionResponse


health_router = APIRouter(tags=["system"])
router = APIRouter(
    tags=["system"], dependencies=[Depends(require_http_token)],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
System = Annotated[SystemService, Depends(get_system_service)]
Updates = Annotated[UpdateService, Depends(get_update_service)]


@health_router.get("/health", response_model=HealthResponse, operation_id="get_health")
def health(service: System):
    return service.get_health()


@router.get("/version", response_model=VersionResponse, operation_id="get_version")
def version(service: System):
    return service.get_version()


@router.get(
    "/update/check", response_model=UpdateResponse, operation_id="check_update",
    responses={502: {"model": ErrorResponse}},
)
def check_update(service: Updates):
    return service.check()


@router.post(
    "/shutdown", response_model=ShutdownResponse, operation_id="shutdown", status_code=202,
    responses={503: {"model": ErrorResponse}},
)
def shutdown(service: System):
    return service.request_shutdown()
