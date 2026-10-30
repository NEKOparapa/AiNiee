from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ModuleFolders.Application.AnalysisService import AnalysisService
from Server.deps import get_analysis_service, require_http_token
from Server.schemas.analysis import AnalysisDocument, AnalysisImportRequest, AnalysisImportResponse, AnalysisMoveRequest, AnalysisPublishRequest, AnalysisPublishResponse, AnalysisView
from Server.schemas.system import ErrorResponse
from Server.schemas.tables import TableDownload


router = APIRouter(tags=["analysis"], dependencies=[Depends(require_http_token)], responses={
    status: {"model": ErrorResponse} for status in (400, 401, 404, 409, 500)
})
Service = Annotated[AnalysisService, Depends(get_analysis_service)]


@router.get("/projects/current/analysis", response_model=AnalysisDocument, response_model_exclude_unset=True, operation_id="get_project_analysis")
def get_analysis(service: Service):
    return service.get()


@router.put("/projects/current/analysis", response_model=AnalysisDocument, response_model_exclude_unset=True, operation_id="put_project_analysis")
def put_analysis(body: AnalysisDocument, service: Service):
    return service.put(body.model_dump())


@router.post("/projects/current/analysis/{view}/import", response_model=AnalysisImportResponse, response_model_exclude_unset=True, operation_id="import_project_analysis")
def import_analysis(view: AnalysisView, body: AnalysisImportRequest, service: Service):
    return service.import_rows(view, body.content_base64, body.project_id)


@router.get("/projects/current/analysis/{view}/export", response_model=TableDownload, operation_id="export_project_analysis")
def export_analysis(view: AnalysisView, service: Service, category: str | None = None, q: Annotated[str, Query(max_length=4096)] = "", project_id: str | None = None):
    return service.export_rows(view, category, q, project_id)


@router.post("/projects/current/analysis/{view}/publish", response_model=AnalysisPublishResponse, response_model_exclude_unset=True, operation_id="publish_project_analysis")
def publish_analysis(view: AnalysisView, body: AnalysisPublishRequest, service: Service):
    return service.publish(view, body.project_id, body.table_id, body.identities)


@router.post("/projects/current/analysis/{view}/move", response_model=AnalysisDocument, response_model_exclude_unset=True, operation_id="move_project_analysis")
def move_analysis(view: AnalysisView, body: AnalysisMoveRequest, service: Service):
    return service.move(view, body.project_id, body.target, body.category, body.identities)
