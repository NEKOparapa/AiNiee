from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.PlatformService import PlatformService
from Server.deps import get_platform_service, require_http_token
from Server.schemas.platforms import (
    PlatformBindings,
    PlatformCreate,
    PlatformDeleteResponse,
    PlatformListResponse,
    PlatformModelsResponse,
    PlatformResponse,
    PlatformTestResponse,
    PlatformUpdate,
)
from Server.schemas.system import ErrorResponse, ValidationErrorResponse


router = APIRouter(
    tags=["platforms"], dependencies=[Depends(require_http_token)],
    responses={
        **{status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 502)},
        422: {"model": ErrorResponse | ValidationErrorResponse},
    },
)
Service = Annotated[PlatformService, Depends(get_platform_service)]


@router.get("/platforms", response_model=PlatformListResponse, operation_id="list_platforms")
def list_platforms(service: Service):
    return service.list_platforms()


@router.post("/platforms", response_model=PlatformResponse, status_code=201, operation_id="create_platform")
def create_platform(data: PlatformCreate, service: Service):
    return service.create_platform(data.model_dump(exclude_unset=True))


@router.put("/platforms/bindings", response_model=PlatformBindings, operation_id="update_platform_bindings")
def update_bindings(bindings: PlatformBindings, service: Service):
    return service.update_bindings(bindings.model_dump())


@router.put("/platforms/{platform_id}", response_model=PlatformResponse, operation_id="update_platform")
def update_platform(platform_id: str, data: PlatformUpdate, service: Service):
    return service.update_platform(platform_id, data.model_dump(exclude_unset=True))


@router.delete("/platforms/{platform_id}", response_model=PlatformDeleteResponse, operation_id="delete_platform")
def delete_platform(platform_id: str, service: Service):
    return service.delete_platform(platform_id)


@router.get("/platforms/{platform_id}/models", response_model=PlatformModelsResponse, operation_id="get_platform_models")
def get_models(platform_id: str, service: Service):
    return service.get_models(platform_id)


@router.post("/platforms/{platform_id}/test", response_model=PlatformTestResponse, operation_id="test_platform")
def test_platform(platform_id: str, service: Service):
    return service.test_platform(platform_id)
