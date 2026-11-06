"""Resumable media stages serialized through each project's media queue."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from starlette.concurrency import run_in_threadpool
from pydantic import Field, ValidationError

from Backend.api.schemas import RequestModel
from Backend.api.image_generation_schemas import ImageGenerationOptions, GeneratedImageWriteOptions
from Backend.api.audio_schemas import TranscriptionOptions, SubtitleOptions
from Backend.api.pipeline_schemas import TranslationOptions
from Backend.api.queued import media_lane, run_queued
from Backend.application.pipeline_common import PipelineError
from Backend.application.media_run_scope import MediaRunScope
from Backend.core.log_system import redact


class MediaRunRequest(RequestModel):
    stage: Literal["recognize", "translate", "generate", "preview", "export"]
    operation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,80}$")
    file_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+$",
                                description="仅处理此文件；只支持 recognize/translate/generate，省略时处理整个项目")
    config: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


def _validated(schema, values):
    try:
        validated = schema.model_validate(values)
        result = validated.model_dump(exclude_none=True, exclude_unset=True)
        # An explicit null seed requests randomness over a saved fixed seed.
        if schema is ImageGenerationOptions and "seed" in validated.model_fields_set:
            result["seed"] = validated.seed
        return result
    except ValidationError as error:
        # Validation errors can echo a provider secret from rejected input.
        raise PipelineError("INVALID_MEDIA_OPTIONS", "媒体处理参数无效，请检查接口配置或导出选项", 422) from error


def create_media_operation_router(runtime, authorized):
    router = APIRouter(prefix="/api/v2/media", tags=["Media workspace stages"],
                       dependencies=[Depends(authorized)])

    @router.post("/operations/{operation_id}/stop")
    def stop(operation_id: str):
        return runtime.stop_model_operation(operation_id)

    @router.post("/{workspace_id}/run")
    async def run(workspace_id: str, body: MediaRunRequest, prefer: str | None = Header(default=None)):
        from Backend.application.media_workspace_service import get_media_store

        store = get_media_store(runtime)
        lane = await run_in_threadpool(media_lane, store, workspace_id)
        def action(context):
            from Backend.application.image_generation_service import generate_image_model
            from Backend.application.generated_image_write_service import write_generated_images
            # Reload only after reaching the front of the project's queue.
            workspace = store.load(workspace_id)
            image = workspace["kind"] == "image"
            if image and body.stage not in ("generate", "preview", "export"):
                raise PipelineError("INVALID_MEDIA_STAGE", "图片翻译仅支持单步生图、预览和导出", 422)
            if body.stage == "recognize":
                config = _validated(TranscriptionOptions, body.config)
            elif body.stage == "translate":
                config = _validated(TranslationOptions, body.config)
            elif body.stage == "generate":
                if not image:
                    raise PipelineError("INVALID_MEDIA_STAGE", "生图流程仅支持图片工作区", 422)
                config = _validated(ImageGenerationOptions, body.config)
            elif body.config:
                raise PipelineError("INVALID_MEDIA_OPTIONS", "此步骤不接受识别或翻译配置", 422)
            if body.stage in ("recognize", "translate", "generate") and body.options:
                raise PipelineError("INVALID_MEDIA_OPTIONS", "此步骤不接受导出选项", 422)
            output_values = dict(body.options)
            if image:
                workspace["model"].setdefault("extra", {})["image_translation_mode"] = "generation"
            if body.stage == "preview":
                if not image:
                    raise PipelineError("INVALID_MEDIA_STAGE", "音频字幕可直接预览，无需生成图片", 422)
                options = _validated(GeneratedImageWriteOptions,
                                     {**output_values, "output_dir": workspace["preview_dir"] + "/generation",
                                      "format": "png", "overwrite": True, "save_model": False})
            elif body.stage == "export":
                if workspace["kind"] == "video":
                    from Backend.application.video_translation_service import video_subtitle_options
                    output_values = video_subtitle_options(output_values)
                options = _validated(GeneratedImageWriteOptions if image else SubtitleOptions, output_values)

            scope = MediaRunScope(workspace, body.stage, body.file_id)
            if body.stage in ("recognize", "translate", "generate"):
                config = scope.configure(config)
            prepared = {"model": scope.model}

            def checkpoint(*unused):
                store.save_model(workspace_id, scope.merge(prepared["model"]))

            def on_prepared(model):
                prepared["model"] = model
                checkpoint()

            def progress(value):
                runtime.pipeline_progress({**value, "workspace_id": workspace_id, "stage": body.stage,
                                           "file_id": body.file_id or value.get("file_id")})
                # ASR commits its slice checkpoint before this callback.
                if body.stage == "recognize" and not image:
                    checkpoint()

            context.on_model_prepared = on_prepared
            context.on_batch_complete = checkpoint
            context.on_progress = progress
            result = None
            try:
                if body.stage == "recognize":
                    from Backend.application.transcription_service import transcribe_model
                    result = transcribe_model(prepared["model"], config, context=context)
                elif body.stage == "translate":
                    from Backend.application.translation_service import translate_model
                    result = translate_model(prepared["model"], config, context=context)
                elif body.stage == "generate":
                    result = generate_image_model(prepared["model"], config, context=context)
                elif image:
                    result = write_generated_images(prepared["model"], options, context=context)
                else:
                    from Backend.application.subtitle_service import write_subtitles
                    result = write_subtitles(prepared["model"], options)
                prepared["model"] = result.get("model", prepared["model"])
                model = scope.merge(prepared["model"])
                workspace = store.save_model(workspace_id, model,
                    status=result["status"], report={"stage": body.stage, "file_id": body.file_id, **result["report"]})
                return {"status": result["status"], "workspace": workspace,
                        "report": result["report"], "files": result.get("files", [])}
            except Exception as error:
                report = {**(result.get("report", {}) if isinstance(result, dict) else {}),
                          "stage": body.stage, "file_id": body.file_id}
                report["errors"] = [*report.get("errors", []),
                    {"code": getattr(error, "code", "MEDIA_STAGE_FAILED"), "message": redact(str(error))}]
                # Retain the latest in-memory paid results on exceptional exits too.
                latest = scope.merge(prepared["model"])
                try:
                    workspace = store.save_model(workspace_id, latest, status="failed", report=report)
                except Exception as save_error:
                    report["operation_errors"] = [*report.get("operation_errors", []),
                        {"code": "MEDIA_CHECKPOINT_FAILED", "message": redact(str(save_error))}]
                    # A client can retry saving this exact model. Do not point
                    # its latest model at an older on-disk interchange file.
                    workspace = {**workspace, "model": latest, "status": "failed", "report": report,
                                 "persisted": False, "last_saved_model_path": workspace.get("model_path"),
                                 "model_path": None,
                                 "files": [{**entry, "translated_url": None}
                                           if body.file_id is None or entry["file_id"] == body.file_id else entry
                                           for entry in workspace.get("files", [])]}
                return {"status": "failed", "workspace": workspace, "report": report,
                        "files": result.get("files", []) if isinstance(result, dict) else []}

        return await run_queued(runtime, f"media/{workspace_id}/{body.stage}", action, lane=lane,
                          prefer=prefer, operation_id=body.operation_id, project_id=workspace_id)

    return router
