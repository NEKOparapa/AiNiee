from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.TaskService import TaskService
from Server.deps import get_task_service, require_http_token
from Server.schemas.system import ErrorResponse
from Server.schemas.tasks import TaskCurrentResponse, TaskStartRequest


router = APIRouter(
    tags=["tasks"], dependencies=[Depends(require_http_token)],
    responses={status: {"model": ErrorResponse} for status in (400, 401, 403, 409, 500, 503)},
)
Service = Annotated[TaskService, Depends(get_task_service)]


@router.get(
    "/tasks/current", response_model=TaskCurrentResponse, response_model_exclude_unset=True,
    operation_id="get_current_task",
)
def current_task(service: Service):
    return service.get_current()


@router.post("/tasks/translate", response_model=TaskCurrentResponse, operation_id="start_translation")
def start_translation(body: TaskStartRequest, service: Service):
    return service.translate(body.continue_task)


@router.post("/tasks/polish", response_model=TaskCurrentResponse, operation_id="start_polishing")
def start_polishing(body: TaskStartRequest, service: Service):
    return service.polish(body.continue_task)


@router.post("/tasks/analysis", response_model=TaskCurrentResponse, operation_id="start_analysis")
def start_analysis(service: Service):
    return service.analysis()


@router.post("/tasks/stop", response_model=TaskCurrentResponse, operation_id="stop_task")
def stop_task(service: Service):
    return service.stop()
