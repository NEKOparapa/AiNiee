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
    ImageReadRequest,
)
from Backend.api.queued import require_model_lane, run_queued


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
        if lane == "image":
            from Backend.application.pipeline_common import PipelineError
            raise PipelineError("IMAGE_GENERATION_REQUIRED", "图片翻译仅支持单步生图接口", 422)
        def action(context):
            from Backend.application.translation_service import translate_model
            result = translate_model(model, body.config.model_dump(exclude_none=True), context=context)
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
