"""Translation tools sharing the REST/desktop scheduler, without HTTP callbacks."""
from dataclasses import replace
from functools import lru_cache

from pydantic import ValidationError

from Backend.api.mcp_schemas import (
    DocumentTranslationRequest, MCPAudioTranslationRequest, MCPImageGenerationRequest,
    MCPJobListQuery, MCPJobQuery,
)
from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.log_system import redact


@lru_cache(maxsize=None)
def _field_names(schema):
    """Only schema-defined names, never user-supplied dict keys, enter errors."""
    document = schema.model_json_schema()
    definitions = [document, *document.get("$defs", {}).values()]
    return frozenset(name for definition in definitions for name in definition.get("properties", {}))


def _validate(schema, values):
    try:
        return schema.model_validate(values)
    except ValidationError as error:
        fields = _field_names(schema)
        details = [{"loc": [part if isinstance(part, int) or part in fields else "<field>"
                            for part in issue["loc"]], "type": issue["type"]}
                   for issue in error.errors(include_input=False, include_context=False, include_url=False)]
        raise PipelineError("INVALID_MCP_ARGUMENTS", "MCP 参数不正确，请检查字段与类型", 422, details) from None


def _summary(job, *, result_available=False):
    summary = {key: value for key, value in job.items() if key != "result"}
    if result_available:
        summary["result_available"] = job.get("result") is not None
    return summary


def _progress(context, stage, **values):
    if context.on_progress:
        context.on_progress({"stage": stage, **values})


def _stage_context(context, stage):
    callback = context.on_progress
    return replace(context, on_progress=(
        (lambda values: callback({**values, "stage": stage})) if callback else None
    ))


def _document_pipeline(body, context):
    from Backend.application.read_service import read_document
    from Backend.application.translation_service import translate_model
    from Backend.application.write_service import write_model

    project, files = None, []
    reports, outcomes = {}, {}

    def response(status, stage):
        return {"status": status, "model": project, "files": files,
                "report": {"stage": stage, "stage_status": outcomes, **reports}}

    def prepared(model):
        nonlocal project
        project = model
        if context.on_model_prepared:
            context.on_model_prepared(model)

    stages = ("read", "translation", "write") if body.output is not None else ("read", "translation")
    for stage in stages:
        if context.is_cancelled():
            return response("cancelled", stage)
        _progress(context, stage, state="running")
        try:
            if stage == "read":
                result = read_document(body.path, body.read_options.model_dump())
            elif stage == "translation":
                scoped = replace(_stage_context(context, stage), on_model_prepared=prepared)
                result = translate_model(project, body.translation.model_dump(exclude_none=True), context=scoped)
            else:
                result = write_model(project, body.output.model_dump(exclude_none=True))
            project = result.get("model", project)
            files = result.get("files", files)
            reports[stage], outcomes[stage] = result["report"], result["status"]
            if result["report"].get("operation_errors"):
                status = result["status"] if result["status"] in ("partial", "failed") else "failed"
                return response(status, stage)
            # Keep the latest usable model. Partial work needs review/resumption;
            # do not silently pay for or export another stage after it.
            if result["status"] != "success":
                return response(result["status"], stage)
            if context.is_cancelled():
                return response("cancelled", stage)
        except Exception as error:
            if project is None:
                raise
            reports[stage] = {"errors": [{"code": getattr(error, "code", "DOCUMENT_STAGE_FAILED"),
                                          "message": redact(str(error))}]}
            outcomes[stage] = "failed"
            return response("failed", stage)
    _progress(context, "completed", state="success")
    return response("success", "completed")


class MCPTranslationService:
    def __init__(self, runtime):
        self.runtime = runtime

    def _submit(self, name, lane, body, action):
        context = ExecutionContext(source="mcp", on_progress=self.runtime.pipeline_progress)
        job = self.runtime.run_job(name, action, lane=lane, source="mcp", context=context,
                                   operation_id=body.request_id, background=True)
        return _summary(job, result_available=True)

    def submit_document(self, requestdict):
        body = _validate(DocumentTranslationRequest, requestdict)
        return self._submit("mcp/document.translate", "document", body,
                            lambda context: _document_pipeline(body, context))

    def submit_image_generation(self, requestdict):
        body = _validate(MCPImageGenerationRequest, requestdict)
        def action(context):
            from Backend.application.image_generation_pipeline_service import translate_image_generation
            _progress(context, "read", state="running")
            callback = context.on_progress
            def progress(values):
                stage = "write" if values.get("operation") == "write_generated_image" else "generation"
                if callback:
                    callback({"stage": stage, **values})
            return translate_image_generation(body.path, read_options=body.read_options.model_dump(),
                         generation=body.generation.model_dump(exclude_unset=True),
                         output=body.output.model_dump(), context=replace(context, on_progress=progress))
        return self._submit("mcp/image.generate", "image", body, action)

    def submit_audio(self, requestdict):
        body = _validate(MCPAudioTranslationRequest, requestdict)
        def action(context):
            from Backend.application.audio_translation_service import translate_audio
            _progress(context, "read", state="running")
            return translate_audio(body.path, read_options=body.read_options.model_dump(),
                                   transcription=body.transcription.model_dump(exclude_none=True),
                                   translation=body.translation.model_dump(exclude_none=True),
                                   output=body.output.model_dump(), context=context)
        return self._submit("mcp/audio.translate", "audio", body, action)

    def get_job(self, job_id, include_result=False):
        query = _validate(MCPJobQuery, {"job_id": job_id, "include_result": include_result})
        job = self.runtime.scheduler.get(query.job_id)
        summary = _summary(job, result_available=True)
        if query.include_result:
            summary["result"] = job.get("result")
        return summary

    def list_jobs(self, lane=None, limit=50):
        query = _validate(MCPJobListQuery, {"lane": lane, "limit": limit})
        return [_summary(job) for job in self.runtime.scheduler.list(lane=query.lane, limit=query.limit)]

    def get_queues(self):
        return self.runtime.scheduler.lanes()

    def cancel_job(self, job_id):
        query = _validate(MCPJobQuery, {"job_id": job_id})
        return _summary(self.runtime.scheduler.cancel(query.job_id), result_available=True)
