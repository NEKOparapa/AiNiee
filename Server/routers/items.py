from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ModuleFolders.Application.ItemService import ItemService
from Server.deps import get_item_service, require_http_token
from Server.schemas.items import ItemListQuery, ItemListResponse, ItemPatchRequest, ItemRecord
from Server.schemas.system import ErrorResponse


router = APIRouter(tags=["items"], dependencies=[Depends(require_http_token)], responses={
    status: {"model": ErrorResponse} for status in (400, 401, 404, 409, 500)
})
Service = Annotated[ItemService, Depends(get_item_service)]


@router.get("/projects/current/items", response_model=ItemListResponse, operation_id="get_project_items")
def get_items(query: Annotated[ItemListQuery, Query()], service: Service):
    return service.list_items(**query.model_dump())


@router.patch("/projects/current/items/{file:path}/{index}", response_model=ItemRecord, operation_id="patch_project_item")
def patch_item(file: str, index: int, body: ItemPatchRequest, service: Service):
    return service.patch_item(file, index, body.model_dump(exclude_unset=True, exclude={"project_id"}), body.project_id)
