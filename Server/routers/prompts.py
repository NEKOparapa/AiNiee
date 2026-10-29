from typing import Annotated

from fastapi import APIRouter, Depends

from ModuleFolders.Application.PromptService import PromptService
from Server.deps import get_prompt_service, require_http_token
from Server.schemas.prompts import LibraryKind, PromptDocument, PromptKind, PromptLibrary, PromptUpsertRequest
from Server.schemas.system import ErrorResponse


router = APIRouter(tags=["prompts"], dependencies=[Depends(require_http_token)], responses={status: {"model": ErrorResponse} for status in (400, 401, 404, 409)})
Service = Annotated[PromptService, Depends(get_prompt_service)]


@router.get("/prompts/{kind}", response_model=PromptDocument, response_model_exclude_unset=True, operation_id="get_prompt")
def get_prompt(kind: PromptKind, service: Service):
    return service.get(kind)


@router.put("/prompts/{kind}", response_model=PromptDocument, response_model_exclude_unset=True, operation_id="put_prompt")
def put_prompt(kind: PromptKind, body: PromptDocument, service: Service):
    return service.put(kind, body.model_dump(exclude_unset=True))


@router.get("/prompt-library", response_model=PromptLibrary, response_model_exclude_unset=True, operation_id="get_prompt_library")
def get_library(kind: LibraryKind, service: Service):
    return service.get_library(kind)


@router.post("/prompt-library", response_model=PromptLibrary, response_model_exclude_unset=True, operation_id="save_library_prompt")
def save_library_prompt(kind: LibraryKind, body: PromptUpsertRequest, service: Service):
    return service.upsert(kind, body.model_dump(exclude_unset=True))


@router.delete("/prompt-library", response_model=PromptLibrary, response_model_exclude_unset=True, operation_id="delete_library_prompt")
def delete_library_prompt(kind: LibraryKind, id: str, service: Service):
    return service.delete(kind, id)
