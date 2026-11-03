"""MCP tools are a transport adapter over the existing application scheduler."""
import json
import logging
from typing import Literal

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import ValidationError, create_model
from starlette.concurrency import run_in_threadpool

from Backend.api.mcp_schemas import (
    DocumentTranslationRequest, MCPAudioTranslationRequest, MCPImageGenerationRequest,
    MCPImageTranslationRequest, MCPJobListQuery, MCPJobQuery,
)
from Backend.api.schemas import RequestModel
from Backend.application.mcp_service import MCPTranslationService
from Backend.application.pipeline_common import PipelineError
from Backend.core.log_system import redact
from Backend.core.protocol import to_wire


def _result(value, *, error=False):
    value = to_wire(value)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(value, ensure_ascii=False))],
        structured_content=value, is_error=error,
    )


def _error(code, message):
    return _result({"error": {"code": code, "message": redact(message)}}, error=True)


class _CancelArguments(RequestModel):
    job_id: str


def create_mcp_server(runtime):
    service = MCPTranslationService(runtime)
    schemas = {
        name: create_model(name + "Arguments", __base__=RequestModel, request=(schema, ...))
        for name, schema in (
            ("submit_document_translation", DocumentTranslationRequest),
            ("submit_image_translation", MCPImageTranslationRequest),
            ("submit_image_generation", MCPImageGenerationRequest),
            ("submit_audio_translation", MCPAudioTranslationRequest),
        )
    }
    schemas.update(get_job=MCPJobQuery, list_jobs=MCPJobListQuery,
                   cancel_job=_CancelArguments, get_queues=RequestModel)

    async def validate_tool_arguments(ctx, call_next):
        # SDK validation messages can contain rejected credential values. Check
        # before SDK dispatch, retain its typed tool schemas, and never echo an
        # invalid request. Unknown top-level arguments cannot be ignored either.
        if ctx.method == "tools/call":
            params = ctx.params if isinstance(ctx.params, dict) else {}
            name = params.get("name")
            schema = schemas.get(name) if isinstance(name, str) else None
            if schema is None:
                return _error("UNKNOWN_MCP_TOOL", "未知 MCP 工具，请先查询工具列表")
            try:
                arguments = params.get("arguments")
                schema.model_validate({} if arguments is None else arguments)
            except ValidationError:
                return _error("INVALID_MCP_ARGUMENTS", "MCP 参数不正确，请按工具定义检查字段与类型")
        return await call_next(ctx)

    server = MCPServer(
        "AiNiee", title="AiNiee Translation", version="1.0.0",
        instructions=(
            "Translate documents (including PDF), images and audio using AiNiee. "
            "Submissions return a job ID immediately. Poll get_job, use include_result=true "
            "only when retrieving the completed model/files, and use cancel_job to stop. "
            "Document/image/audio queues are shared with REST and desktop: each runs one job. "
            "Paths are on the backend machine. Models/providers inherit its saved settings; "
            "prefer provider_id over supplying credentials. Jobs may call paid providers and "
            "write output files. A disconnected MCP client does not stop a submitted job. "
            "Use a unique request_id to identify a submission; duplicate IDs are rejected, "
            "so query the existing job instead of retrying translation."
        ),
        middleware=[validate_tool_arguments],
    )
    submit_hints = ToolAnnotations(read_only_hint=False, destructive_hint=True,
                                  idempotent_hint=False, open_world_hint=True)
    query_hints = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                 idempotent_hint=True, open_world_hint=False)
    cancel_hints = ToolAnnotations(read_only_hint=False, destructive_hint=True,
                                  idempotent_hint=True, open_world_hint=False)

    async def invoke(method, key, *args, **kwargs):
        try:
            value = await run_in_threadpool(method, *args, **kwargs)
            return _result({key: value})
        except PipelineError as error:
            return _error(error.code, error.message)
        except Exception as error:
            # Unexpected exceptions may embed submitted credentials. Log the
            # exception type, not its repr/arguments or the submitted payload.
            logging.getLogger("AiNiee.backend").error("MCP operation failed: %s", type(error).__name__)
            return _error("MCP_OPERATION_FAILED", "MCP 操作失败，请检查后端状态后重试")

    @server.tool(title="提交文档翻译", annotations=submit_hints)
    async def submit_document_translation(request: DocumentTranslationRequest) -> CallToolResult:
        """Queue document/PDF read → translation → optional export. Returns a job ID, not the result.

        path is a backend-local file/directory. read_options.pages selects PDF pages.
        translation inherits saved provider/language settings. Omit output to return only
        the translated model; set output.output_dir to export. request_id is optional.
        """
        return await invoke(service.submit_document, "job", request.model_dump(exclude_unset=True))

    @server.tool(title="提交图片 OCR 翻译", annotations=submit_hints)
    async def submit_image_translation(request: MCPImageTranslationRequest) -> CallToolResult:
        """Queue image read → OCR → translation → render/export on the shared image queue.

        Supply a backend-local path and output.output_dir. OCR and translation inherit
        backend settings; optional request_id identifies this submission.
        """
        return await invoke(service.submit_image, "job", request.model_dump(exclude_unset=True))

    @server.tool(title="提交整图生成翻译", annotations=submit_hints)
    async def submit_image_generation(request: MCPImageGenerationRequest) -> CallToolResult:
        """Queue whole-image translation with the saved generation provider, then export.

        Shares the image queue with OCR translation. Supply backend-local path and
        output.output_dir; optional generation settings override the saved provider.
        """
        return await invoke(service.submit_image_generation, "job", request.model_dump(exclude_unset=True))

    @server.tool(title="提交音频翻译", annotations=submit_hints)
    async def submit_audio_translation(request: MCPAudioTranslationRequest) -> CallToolResult:
        """Queue audio read → transcription → translation → subtitle export.

        Supply backend-local path and output.output_dir. Transcription and translation
        inherit saved backend settings. Runs on the shared audio queue.
        """
        return await invoke(service.submit_audio, "job", request.model_dump(exclude_unset=True))

    @server.tool(title="查询任务进度与结果", annotations=query_hints)
    async def get_job(job_id: str, include_result: bool = False) -> CallToolResult:
        """Get state/progress/error immediately. Set include_result=true to fetch the model/files.

        Poll until succeeded, partial, failed, cancelled or interrupted. Review partial
        results and failures before resubmitting; a successful tool call can describe a failed job.
        """
        return await invoke(service.get_job, "job", job_id, include_result=include_result)

    @server.tool(title="查询任务列表", annotations=query_hints)
    async def list_jobs(lane: Literal["document", "image", "audio"] | None = None,
                        limit: int = 50) -> CallToolResult:
        """List the latest shared REST, desktop and MCP jobs without large results (limit 1–200)."""
        return await invoke(service.list_jobs, "jobs", lane=lane, limit=limit)

    @server.tool(title="取消指定任务", annotations=cancel_hints)
    async def cancel_job(job_id: str) -> CallToolResult:
        """Cancel exactly this shared job. Queued work stops immediately; running work drains first.

        Keep polling a cancelling job until terminal. Cancellation does not undo completed
        provider calls or file writes. Repeated cancellation leaves terminal records unchanged.
        """
        return await invoke(service.cancel_job, "job", job_id)

    @server.tool(title="查询三类队列", annotations=query_hints)
    async def get_queues() -> CallToolResult:
        """Get running and queued jobs for document, image and audio without entering a queue."""
        return await invoke(service.get_queues, "queues")

    return server
