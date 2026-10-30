from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.CheckService import CheckService
from Server.deps import get_check_service, require_http_token
from Server.schemas.checks import CheckResponse, LanguageCheckRequest, RuleCheckRequest, TerminologyCheckRequest
from Server.schemas.system import ErrorResponse


router = APIRouter(tags=["checks"], dependencies=[Depends(require_http_token)], responses={
    status: {"model": ErrorResponse} for status in (400, 401, 409, 500)
})
Service = Annotated[CheckService, Depends(get_check_service)]


@router.post("/checks/rule", response_model=CheckResponse, operation_id="check_rules")
def check_rules(body: RuleCheckRequest, service: Service):
    return service.run_check("rule", body.model_dump(exclude_none=True))


@router.post("/checks/language", response_model=CheckResponse, operation_id="check_language")
def check_language(body: LanguageCheckRequest, service: Service):
    return service.run_check("language", body.model_dump(exclude_none=True))


@router.post("/checks/terminology", response_model=CheckResponse, operation_id="check_terminology")
def check_terminology(body: TerminologyCheckRequest, service: Service):
    return service.run_check("terminology", body.model_dump(exclude_none=True))
