from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from ModuleFolders.Application.TableService import TableService
from Server.deps import get_table_service, require_http_token
from Server.schemas.tables import TableCollection, TableDownload, TableImportRequest, TableName
from Server.schemas.system import ErrorResponse


router = APIRouter(tags=["tables"], dependencies=[Depends(require_http_token)], responses={status: {"model": ErrorResponse} for status in (400, 401, 404, 409, 413)})
Service = Annotated[TableService, Depends(get_table_service)]


@router.get("/tables/{name}", response_model=TableCollection, response_model_exclude_unset=True, operation_id="get_tables")
def get_tables(name: TableName, service: Service):
    return service.get(name)


@router.put("/tables/{name}", response_model=TableCollection, response_model_exclude_unset=True, operation_id="put_tables")
def put_tables(name: TableName, body: TableCollection, service: Service):
    return service.put(name, body.model_dump(exclude_unset=True))


@router.post("/tables/{name}/import", response_model=TableCollection, response_model_exclude_unset=True, operation_id="import_tables")
def import_tables(name: TableName, body: TableImportRequest, service: Service):
    return service.import_file(name, body.model_dump(exclude_unset=True))


@router.get("/tables/{name}/export", response_model=TableDownload, operation_id="export_tables")
def export_tables(name: TableName, service: Service, table_ids: Annotated[list[str] | None, Query()] = None, format: Literal["json", "xlsx"] = "json", bundle: bool = False):
    return service.export_file(name, table_ids, format, bundle)
