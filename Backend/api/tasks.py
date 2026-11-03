"""HTTP adapters for explicit workspace service methods."""
from fastapi import APIRouter, Depends
from Backend.api.legacy_jobs import wait_document_call

from Backend.api.task_schemas import (
    ApiTestRequest, ExportRequest, GlossaryRequest, TablePolishRequest,
    TableProofreadRequest, TableTranslateRequest, TranslationStart,
)


def create_task_router(runtime, authorized):
    router = APIRouter(prefix="/api", tags=["Workspace operations"], dependencies=[Depends(authorized)])

    @router.post("/tasks/translation", status_code=202)
    def translate(body: TranslationStart):
        return runtime.start_translation(body.continue_status)

    @router.post("/tasks/analysis", status_code=202)
    def analyze():
        return runtime.start_analysis()

    @router.post("/tasks/table/translate", status_code=202)
    def translate_table(body: TableTranslateRequest):
        return runtime.start_table_translation(body.model_dump(exclude_none=True))

    @router.post("/tasks/table/polish", status_code=202)
    def polish_table(body: TablePolishRequest):
        return runtime.start_table_polishing(body.model_dump(exclude_none=True))

    @router.post("/tasks/table/proofread", status_code=202)
    def proofread_table(body: TableProofreadRequest):
        return runtime.start_table_proofreading(body.model_dump(exclude_none=True))

    @router.post("/tasks/glossary/translate", status_code=202)
    def translate_glossary(body: GlossaryRequest):
        return runtime.start_glossary_translation(body.model_dump(exclude_none=True))

    @router.post("/tasks/api-test", status_code=202)
    def test_api(body: ApiTestRequest):
        return runtime.start_api_test(body.model_dump(exclude_none=True))

    @router.post("/project/export", status_code=202)
    def export(body: ExportRequest):
        return runtime.start_export(body.model_dump(exclude_none=True))

    @router.post("/project/save")
    async def save():
        return await wait_document_call(runtime.save_project)

    @router.post("/tasks/stop")
    def stop():
        return runtime.stop()

    return router
