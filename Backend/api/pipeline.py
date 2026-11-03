"""Model-in/model-out endpoints backed by the shared project queues."""
from fastapi import APIRouter, Depends, Header

from Backend.api.pipeline_schemas import (
    DocumentReadRequest, ModelResponse,
    TranslateRequest, WriteRequest, WriteResponse,
)
from Backend.api.audio_schemas import (
    AudioReadRequest, AudioTranslateRequest, AudioTranslateResponse,
    SubtitleWriteRequest, TranscribeRequest,
)
from Backend.api.image_schemas import (
    ImageReadRequest, ImageDetectRequest, OcrRequest, ImageWriteRequest, ImageTranslateRequest, ImagePipelineResponse,
)
from Backend.api.queued import require_model_lane, run_queued
from Backend.application.image_workflow import record_image_stage


def create_pipeline_router(runtime, authorized):
    router = APIRouter(prefix="/api/v2", tags=["Translation pipeline"],
                       dependencies=[Depends(authorized)])

    @router.post("/read/document", response_model=ModelResponse)
    async def read_document(body: DocumentReadRequest, prefer: str | None = Header(default=None)):
        def action(context):
            from Backend.application.read_service import read_document as read
            return read(body.path, body.options.model_dump())
        return await run_queued(runtime, "read/document", action, lane="document", prefer=prefer)

    @router.post("/read/image", response_model=ModelResponse)
    async def read_image(body: ImageReadRequest, prefer: str | None = Header(default=None)):
        def action(context):
            from Backend.application.image_read_service import read_image as read
            return read(body.path, body.options.model_dump(), context=context)
        return await run_queued(runtime, "read/image", action, lane="image", prefer=prefer)

    @router.post("/ocr", response_model=ModelResponse)
    async def ocr(body: OcrRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        require_model_lane(runtime, model, "image")
        def action(context):
            from Backend.application.ocr_service import ocr_model
            record_image_stage(model, "recognize", "running")
            result = ocr_model(model, body.config.model_dump(exclude_none=True), context=context)
            record_image_stage(result["model"], "recognize", result["status"])
            return result
        return await run_queued(runtime, "ocr", action, lane="image", prefer=prefer,
                          project_id=model.get("project_id"))

    @router.post("/image/detect", response_model=ModelResponse)
    async def detect_image(body: ImageDetectRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        require_model_lane(runtime, model, "image")
        def action(context):
            from Backend.application.image_detection_service import detect_images
            return detect_images(model, context=context)
        return await run_queued(runtime, "image/detect", action, lane="image", prefer=prefer,
                          project_id=model.get("project_id"))

    async def image_stage(body, stage, prefer):
        model = body.model.model_dump()
        require_model_lane(runtime, model, "image")
        def action(context):
            from Backend.application.image_render_service import repair_images, render_images, export_images
            service = {"repair": repair_images, "render": render_images, "export": export_images}[stage]
            return service(model, body.options.model_dump(exclude_none=True, exclude_unset=True), context=context)
        return await run_queued(runtime, "image/" + stage, action, lane="image", prefer=prefer,
                          project_id=model.get("project_id"))

    @router.post("/image/repair", response_model=ImagePipelineResponse)
    async def repair_image(body: ImageWriteRequest, prefer: str | None = Header(default=None)):
        return await image_stage(body, "repair", prefer)

    @router.post("/image/render", response_model=ImagePipelineResponse)
    async def render_image(body: ImageWriteRequest, prefer: str | None = Header(default=None)):
        return await image_stage(body, "render", prefer)

    @router.post("/image/export", response_model=ImagePipelineResponse)
    async def export_image(body: ImageWriteRequest, prefer: str | None = Header(default=None)):
        return await image_stage(body, "export", prefer)

    @router.post("/write/image", response_model=ImagePipelineResponse)
    async def write_image(body: ImageWriteRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        require_model_lane(runtime, model, "image")
        def action(context):
            from Backend.application.image_write_service import write_images
            return write_images(model, body.options.model_dump(exclude_none=True), context=context)
        return await run_queued(runtime, "write/image", action, lane="image", prefer=prefer,
                          project_id=model.get("project_id"))

    @router.post("/image/translate", response_model=ImagePipelineResponse)
    async def translate_image(body: ImageTranslateRequest, prefer: str | None = Header(default=None)):
        def action(context):
            from Backend.application.image_translation_service import translate_image as run
            return run(body.path, read_options=body.read_options.model_dump(),
                       ocr=body.ocr.model_dump(exclude_none=True),
                       translation=body.translation.model_dump(exclude_none=True),
                       output=body.output.model_dump(exclude_none=True), context=context)
        return await run_queued(runtime, "image/translate", action, lane="image", prefer=prefer)

    @router.post("/read/audio", response_model=ModelResponse)
    async def read_audio(body: AudioReadRequest, prefer: str | None = Header(default=None)):
        def action(context):
            from Backend.application.audio_read_service import read_audio as read
            return read(body.path, body.options.model_dump())
        return await run_queued(runtime, "read/audio", action, lane="audio", prefer=prefer)

    @router.post("/transcribe", response_model=ModelResponse)
    async def transcribe(body: TranscribeRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        require_model_lane(runtime, model, "audio")
        def action(context):
            from Backend.application.transcription_service import transcribe_model
            return transcribe_model(model, body.config.model_dump(exclude_none=True), context=context)
        return await run_queued(runtime, "transcribe", action, lane="audio", prefer=prefer,
                          project_id=model.get("project_id"))

    @router.post("/write/subtitles", response_model=WriteResponse)
    async def write_subtitles(body: SubtitleWriteRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        require_model_lane(runtime, model, "audio")
        def action(context):
            from Backend.application.subtitle_service import write_subtitles as write
            return write(model, body.options.model_dump())
        return await run_queued(runtime, "write/subtitles", action, lane="audio", prefer=prefer,
                          project_id=model.get("project_id"))

    @router.post("/audio/translate", response_model=AudioTranslateResponse)
    async def translate_audio(body: AudioTranslateRequest, prefer: str | None = Header(default=None)):
        def action(context):
            from Backend.application.audio_translation_service import translate_audio as run
            return run(body.path, read_options=body.read_options.model_dump(),
                       transcription=body.transcription.model_dump(exclude_none=True),
                       translation=body.translation.model_dump(exclude_none=True),
                       output=body.output.model_dump(), context=context)
        return await run_queued(runtime, "audio/translate", action, lane="audio", prefer=prefer)

    @router.post("/translate", response_model=ModelResponse)
    async def translate(body: TranslateRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        lane = runtime.lane_for_model(model)
        def action(context):
            from Backend.application.translation_service import translate_model
            if lane == "image":
                record_image_stage(model, "translate", "running")
            result = translate_model(model, body.config.model_dump(exclude_none=True), context=context)
            if lane == "image":
                record_image_stage(result["model"], "translate", result["status"])
            return result
        return await run_queued(runtime, "translate", action, lane=lane, prefer=prefer,
                          project_id=model.get("project_id"))

    @router.post("/write", response_model=WriteResponse)
    async def write(body: WriteRequest, prefer: str | None = Header(default=None)):
        model = body.model.model_dump()
        lane = require_model_lane(runtime, model, "document")
        def action(context):
            from Backend.application.write_service import write_model
            return write_model(model, body.options.model_dump(exclude_none=True))
        return await run_queued(runtime, "write", action, lane=lane, prefer=prefer,
                          project_id=model.get("project_id"))

    return router
