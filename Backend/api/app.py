"""FastAPI transport. Run one process owning four serial project queues."""
import asyncio
import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Route

from Backend.api.events import EventHub
from Backend.api.error_logging import log_request_error, log_validation_error, validation_details
from Backend.api.legacy_jobs import wait_document_call
from Backend.api.schemas import CacheCall, ConfigPatch, EditorCall, FolderQuery, ModelQuery, ProjectLoad
from Backend.application.runtime import BusyError, Runtime
from Backend.application.pipeline_common import PipelineError
from Backend.core.protocol import PROTOCOL_VERSION


def config_document(config):
    revision = hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"config": config, "revision": revision}


def create_app(runtime=None, token=None):
    runtime = runtime or Runtime()
    token = os.environ.get("AINIEE_API_TOKEN", "") if token is None else token
    hub = EventHub()
    from Backend.api.mcp_server import create_mcp_server
    from Backend.api.mcp_security import MCPAuthMiddleware, transport_security_from_env
    mcp_server = create_mcp_server(runtime)
    mcp_http = mcp_server.streamable_http_app(
        streamable_http_path="/mcp", json_response=True, stateless_http=True,
        transport_security=transport_security_from_env(),
    )

    @asynccontextmanager
    async def lifespan(app):
        hub.loop = asyncio.get_running_loop()
        runtime.publish = hub.publish
        await run_in_threadpool(runtime.start)
        try:
            # Mounted ASGI applications do not receive FastAPI's lifespan.
            # Start the SDK manager exactly once, sharing this same Runtime.
            async with mcp_server.session_manager.run():
                yield
        finally:
            await run_in_threadpool(runtime.close)
            hub.loop = None

    app = FastAPI(title="AiNiee Backend", version="2.0.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.mcp_server = mcp_server
    app.state.hub = hub
    app.state.shutdown = None

    def authorized(authorization: str | None = Header(default=None)):
        if token and not secrets.compare_digest(authorization or "", f"Bearer {token}"):
            raise HTTPException(401, "后端访问令牌无效")

    @app.exception_handler(BusyError)
    async def busy_error(request, error):
        log_request_error(request, "BACKEND_BUSY", str(error))
        return JSONResponse(status_code=409, content={
            "detail": str(error), "error": {"code": "BACKEND_BUSY", "message": str(error)},
        })

    @app.exception_handler(PipelineError)
    async def pipeline_error(request, error):
        log_request_error(request, error.code, error.message)
        return JSONResponse(status_code=error.status_code, content={
            "detail": error.message, "error": error.to_dict(),
        })

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        log_request_error(request, "INVALID_REQUEST", str(error))
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        log_request_error(request, f"HTTP_{error.status_code}", str(error.detail))
        return await http_exception_handler(request, error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = validation_details(error)
        log_validation_error(request, details)
        return JSONResponse(status_code=422, content={"detail": details})

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        log_request_error(request, "INTERNAL_ERROR", str(error), error=error)
        return JSONResponse(status_code=500, content={"detail": "后端内部错误，请查看运行日志",
            "error": {"code": "INTERNAL_ERROR", "message": "后端内部错误，请查看运行日志"}})

    @app.get("/health", dependencies=[Depends(authorized)])
    def health():
        return {"service": "AiNiee", "protocol": PROTOCOL_VERSION}

    @app.post("/api/editor/{operation}", dependencies=[Depends(authorized)])
    def editor(operation: str, body: EditorCall):
        from Backend.application.editor import evaluate
        return evaluate(operation, body.args, body.kwargs)

    @app.get("/api/project/preflight/{role}", dependencies=[Depends(authorized)])
    def preflight(role: str):
        from Backend.domain.config.task_config import TaskConfig
        if role not in ("translate", "polish"):
            raise ValueError("未知任务角色")
        from Backend.core.config import config_snapshot
        with config_snapshot(TaskConfig.read_snapshot()):
            config = TaskConfig()
            config.initialize(role)
        tag = config.get_active_platform_tag(role)
        return {"selected_tag": tag, "exists": tag in (getattr(config, "platforms", {}) or {})}

    @app.get("/api/config", dependencies=[Depends(authorized)])
    def get_config():
        return config_document(runtime.load_config())

    @app.get("/api/config/info", dependencies=[Depends(authorized)])
    def config_info():
        return runtime.get_config_info()

    @app.get("/api/config/defaults/{section}", dependencies=[Depends(authorized)])
    def config_defaults(section: str):
        return runtime.get_default_section(section)

    @app.get("/api/config/platform-presets", dependencies=[Depends(authorized)])
    def platform_presets():
        return runtime.get_platform_presets()

    @app.get("/api/config/prompt-presets/{kind}", dependencies=[Depends(authorized)])
    def prompt_presets(kind: str):
        return runtime.get_prompt_presets(kind)

    @app.post("/api/config/import", dependencies=[Depends(authorized)])
    def import_config(body: FolderQuery):
        with runtime.lock:
            return config_document(runtime.import_config(body.path))

    @app.post("/api/config/export", dependencies=[Depends(authorized)])
    def export_config(body: FolderQuery):
        return runtime.export_config(body.path)

    @app.patch("/api/config", dependencies=[Depends(authorized)])
    def patch_config(body: ConfigPatch):
        runtime._validate_mcp_settings(body.values)
        with runtime.lock, runtime.CONFIG_FILE_LOCK:
            current = config_document(runtime.load_config())
            if body.revision is not None and body.revision != current["revision"]:
                raise HTTPException(409, "配置已更新，请重新读取后重试")
            if all(key in current["config"] and current["config"][key] == value for key, value in body.values.items()):
                return current
            if body.table_update:
                return config_document(runtime.update_config(lambda config: config.update(body.values)))
            return config_document(runtime.save_config(body.values, _table_update=body.table_update))

    @app.get("/api/status", dependencies=[Depends(authorized)])
    def status():
        return runtime.status()

    @app.get("/api/project", dependencies=[Depends(authorized)])
    def project():
        return {"project": runtime.snapshot()}

    @app.get("/api/project/types", dependencies=[Depends(authorized)])
    def project_types():
        return runtime.reader.get_support_project_types()

    @app.post("/api/project/load", dependencies=[Depends(authorized)])
    async def load_project(body: ProjectLoad):
        return {"project": await wait_document_call(runtime.load_project, body.project_type, body.input_path, body.exclude_rule)}

    @app.post("/api/cache/{method}", dependencies=[Depends(authorized)])
    async def cache_call(method: str, body: CacheCall):
        execute = run_in_threadpool if method in ("list_project_histories", "search_items") else wait_document_call
        return await execute(runtime.cache_call, method, body.args, body.kwargs, body.project_id)

    @app.post("/api/check/{kind}", dependencies=[Depends(authorized)])
    async def check(kind: str, params: dict[str, Any]):
        return await wait_document_call(runtime.check, kind, params)

    @app.post("/api/shutdown", dependencies=[Depends(authorized)])
    def shutdown():
        with runtime.lock:
            queues = runtime.scheduler.lanes()
            if any(job["source"] in ("api", "mcp") for queue in queues.values()
                   for job in ([queue["running"]] if queue["running"] else []) + queue["queued"]):
                raise PipelineError("BACKEND_BUSY", "外部接口仍在执行，请等待完成后关闭后端", 409)
            if app.state.shutdown is None:
                raise HTTPException(409, "此启动方式不支持远程关闭")
            was_closing = runtime.closing
            runtime.closing = True
            try:
                app.state.shutdown()
            except Exception:
                runtime.closing = was_closing
                raise
        return {"status": "stopping"}

    @app.post("/api/models", dependencies=[Depends(authorized)])
    def models(body: ModelQuery):
        from Backend.infrastructure.llm.catalog import compatible_models, google_models
        try:
            return google_models(body.google_config) if body.google_config is not None else compatible_models(body.url, body.headers)
        except Exception as error:
            raise HTTPException(502, "获取模型失败，请检查接口地址、密钥和后端网络") from error

    @app.post("/api/names", dependencies=[Depends(authorized)])
    def names(body: FolderQuery):
        from pathlib import Path
        from Backend.application.name_extractor import NameExtractor
        if not Path(body.path).is_dir():
            raise HTTPException(400, "后端无法访问该目录")
        return NameExtractor().extract_names_from_folder(body.path)

    @app.websocket("/ws/events")
    async def events(socket: WebSocket):
        if token and not secrets.compare_digest(socket.headers.get("authorization", ""), f"Bearer {token}"):
            await socket.close(code=1008)
            return
        await socket.accept()
        queue = asyncio.Queue(maxsize=256)
        hub.clients.add(queue)
        try:
            await socket.send_json({"type": "connected", "status": runtime.status()})
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=2)
                except asyncio.TimeoutError:
                    message = {"type": "status", "status": runtime.status()}
                await socket.send_json(message)
                if message["type"] == "resync":
                    await socket.close(code=1013)
                    break
        except (WebSocketDisconnect, OSError, RuntimeError):
            pass
        finally:
            hub.clients.discard(queue)

    from Backend.api.pipeline import create_pipeline_router
    app.include_router(create_pipeline_router(runtime, authorized))
    from Backend.api.image_generation import create_image_generation_router
    app.include_router(create_image_generation_router(runtime, authorized))
    from Backend.api.media import create_media_router
    app.include_router(create_media_router(runtime, authorized))
    from Backend.api.tasks import create_task_router
    app.include_router(create_task_router(runtime, authorized))
    from Backend.api.media_operations import create_media_operation_router
    app.include_router(create_media_operation_router(runtime, authorized))
    from Backend.api.jobs import create_job_router
    app.include_router(create_job_router(runtime, authorized))
    # A concrete ASGI route preserves /mcp exactly, without a redirect to /mcp/.
    # FastAPI route dependencies do not protect an ASGI app: authenticate every
    # request here, before the SDK processes its protocol or session headers.
    app.router.routes.append(Route(
        "/mcp", endpoint=MCPAuthMiddleware(mcp_http, token, is_enabled=lambda: runtime.mcp_enabled),
        methods=["GET", "POST", "DELETE", "OPTIONS"],
    ))
    return app


app = create_app()
