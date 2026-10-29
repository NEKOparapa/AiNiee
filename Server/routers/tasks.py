from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.TaskService import TaskService
from Server.deps import get_task_service, require_http_token
from Server.schemas.system import ErrorResponse
from Server.schemas.tasks import TaskCurrentResponse


router = APIRouter(
    tags=["tasks"], dependencies=[Depends(require_http_token)],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
Service = Annotated[TaskService, Depends(get_task_service)]


@router.get(
    "/tasks/current", response_model=TaskCurrentResponse, response_model_exclude_unset=True,
    operation_id="get_current_task",
)
def current_task(service: Service):
    return service.get_current()
