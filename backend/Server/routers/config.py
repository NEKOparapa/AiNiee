from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.ConfigService import ConfigService
from Server.deps import get_config_service, require_http_token
from Server.schemas.config import ConfigDocument, ConfigPatch
from Server.schemas.system import ErrorResponse


router = APIRouter(
    tags=["config"], dependencies=[Depends(require_http_token)],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
Service = Annotated[ConfigService, Depends(get_config_service)]


@router.get("/config", response_model=ConfigDocument, operation_id="get_config")
def get_config(service: Service):
    return service.get_config()


@router.patch("/config", response_model=ConfigDocument, operation_id="patch_config")
def patch_config(changes: ConfigPatch, service: Service):
    return service.patch_config(changes.model_dump(exclude_unset=True))
