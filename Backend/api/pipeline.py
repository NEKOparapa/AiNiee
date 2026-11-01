"""Synchronous model-in/model-out endpoints; admission is owned by Runtime."""
from fastapi import APIRouter, Depends

from Backend.api.pipeline_schemas import (
    DocumentReadRequest, MediaReadRequest, ModelResponse, PdfReadRequest,
    TranslateRequest, WriteRequest, WriteResponse,
)
from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.protocol import to_wire


def create_pipeline_router(runtime, authorized):
    router = APIRouter(prefix="/api/v2", tags=["Translation pipeline"],
                       dependencies=[Depends(authorized)])

    @router.post("/read/document", response_model=ModelResponse)
    def read_document(body: DocumentReadRequest):
        from Backend.application.read_service import read_document as read
        with runtime.operation("read/document", context=ExecutionContext()):
            return to_wire(read(body.path, body.options.model_dump()))

    @router.post("/read/pdf", response_model=ModelResponse)
    def read_pdf(body: PdfReadRequest):
        from Backend.application.read_service import read_pdf as read
        with runtime.operation("read/pdf", context=ExecutionContext()):
            return to_wire(read(body.path, body.options.model_dump(exclude_none=True)))

    @router.post("/read/image")
    def read_image(body: MediaReadRequest):
        raise PipelineError("IMAGE_READ_NOT_IMPLEMENTED", "图片读取尚未实现", 501)

    @router.post("/read/audio")
    def read_audio(body: MediaReadRequest):
        raise PipelineError("AUDIO_READ_NOT_IMPLEMENTED", "音频读取尚未实现", 501)

    @router.post("/translate", response_model=ModelResponse)
    def translate(body: TranslateRequest):
        from Backend.application.translation_service import translate_model
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("translate", context=context):
            return to_wire(translate_model(body.model.model_dump(),
                                           body.config.model_dump(exclude_none=True), context=context))

    @router.post("/write", response_model=WriteResponse)
    def write(body: WriteRequest):
        from Backend.application.write_service import write_model
        with runtime.operation("write", context=ExecutionContext()):
            return to_wire(write_model(body.model.model_dump(), body.options.model_dump(exclude_none=True)))

    return router
