"""Synchronous model-in/model-out endpoints; admission is owned by Runtime."""
from fastapi import APIRouter, Depends

from Backend.api.pipeline_schemas import (
    DocumentReadRequest, ModelResponse, PdfReadRequest,
    TranslateRequest, WriteRequest, WriteResponse,
)
from Backend.api.audio_schemas import (
    AudioReadRequest, AudioTranslateRequest, AudioTranslateResponse,
    SubtitleWriteRequest, TranscribeRequest,
)
from Backend.api.image_schemas import (
    ImageReadRequest, OcrRequest, ImageWriteRequest, ImageTranslateRequest, ImagePipelineResponse,
)
from Backend.application.execution_context import ExecutionContext
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

    @router.post("/read/image", response_model=ModelResponse)
    def read_image(body: ImageReadRequest):
        from Backend.application.image_read_service import read_image as read
        with runtime.operation("read/image", context=ExecutionContext()):
            return to_wire(read(body.path, body.options.model_dump()))

    @router.post("/ocr", response_model=ModelResponse)
    def ocr(body: OcrRequest):
        from Backend.application.ocr_service import ocr_model
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("ocr", context=context):
            return to_wire(ocr_model(body.model.model_dump(), body.config.model_dump(exclude_none=True), context=context))

    @router.post("/write/image", response_model=ImagePipelineResponse)
    def write_image(body: ImageWriteRequest):
        from Backend.application.image_write_service import write_images
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("write/image", context=context):
            return to_wire(write_images(body.model.model_dump(), body.options.model_dump(exclude_none=True), context=context))

    @router.post("/image/translate", response_model=ImagePipelineResponse)
    def translate_image(body: ImageTranslateRequest):
        from Backend.application.image_translation_service import translate_image as run
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("image/translate", context=context):
            return to_wire(run(body.path, read_options=body.read_options.model_dump(),
                               ocr=body.ocr.model_dump(exclude_none=True),
                               translation=body.translation.model_dump(exclude_none=True),
                               output=body.output.model_dump(exclude_none=True), context=context))

    @router.post("/read/audio", response_model=ModelResponse)
    def read_audio(body: AudioReadRequest):
        from Backend.application.audio_read_service import read_audio as read
        with runtime.operation("read/audio", context=ExecutionContext()):
            return to_wire(read(body.path, body.options.model_dump()))

    @router.post("/transcribe", response_model=ModelResponse)
    def transcribe(body: TranscribeRequest):
        from Backend.application.transcription_service import transcribe_model
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("transcribe", context=context):
            return to_wire(transcribe_model(body.model.model_dump(),
                                           body.config.model_dump(exclude_none=True), context=context))

    @router.post("/write/subtitles", response_model=WriteResponse)
    def write_subtitles(body: SubtitleWriteRequest):
        from Backend.application.subtitle_service import write_subtitles as write
        with runtime.operation("write/subtitles", context=ExecutionContext()):
            return to_wire(write(body.model.model_dump(), body.options.model_dump()))

    @router.post("/audio/translate", response_model=AudioTranslateResponse)
    def translate_audio(body: AudioTranslateRequest):
        from Backend.application.audio_translation_service import translate_audio as run
        context = ExecutionContext(on_progress=runtime.pipeline_progress)
        with runtime.operation("audio/translate", context=context):
            return to_wire(run(
                body.path, read_options=body.read_options.model_dump(),
                transcription=body.transcription.model_dump(exclude_none=True),
                translation=body.translation.model_dump(exclude_none=True),
                output=body.output.model_dump(), context=context,
            ))

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
