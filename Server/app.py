"""FastAPI composition; business operations live in Application services."""

import asyncio
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.responses import JSONResponse

from ModuleFolders.Application.Bootstrap import ApplicationRuntime, bootstrap
from ModuleFolders.Application.ConfigService import ConfigService
from ModuleFolders.Application.SystemService import ShutdownUnavailableError, SystemService
from ModuleFolders.Application.UpdateService import UpdateCheckError, UpdateService
from ModuleFolders.Base.EventManager import EventManager
from Server.deps import TokenAuthMiddleware
from Server.event_bridge import EventBridge
from Server.routers import config, system
from Server.schemas.events import WebSocketMessage
from Server.ws import router as websocket_router


DEV_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")


def create_app(
    token: str,
    *,
    allowed_origins: Sequence[str] | None = None,
    shutdown_callback: Callable[[], None] | None = None,
    runtime_factory: Callable[[], ApplicationRuntime] = bootstrap,
) -> FastAPI:
    if not token or any(character.isspace() for character in token):
        raise ValueError("token must be non-empty and contain no whitespace")
    origins = tuple(DEV_ORIGINS if allowed_origins is None else allowed_origins)
    if any(origin == "*" or origin == "null" for origin in origins):
        raise ValueError("CORS requires explicit trusted origins")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime = await run_in_threadpool(runtime_factory)
        bridge = EventBridge(EventManager.get_singleton(), asyncio.get_running_loop())
        try:
            app.state.runtime = runtime
            app.state.event_bridge = bridge
            app.state.config_service = ConfigService()
            app.state.system_service = SystemService(shutdown_callback)
            app.state.update_service = UpdateService()
            bridge.start()
            yield
        finally:
            await bridge.close()
            await run_in_threadpool(runtime.close)

    app = FastAPI(
        title="AiNiee API", version=SystemService().get_version()["version"],
        lifespan=lifespan, docs_url=None, redoc_url=None,
        middleware=[
            Middleware(TokenAuthMiddleware, token=token, allowed_origins=origins),
            Middleware(
                CORSMiddleware, allow_origins=origins,
                allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                allow_headers=["Authorization", "Content-Type"],
            ),
        ],
    )
    app.state.token = token
    app.state.allowed_origins = origins
    app.include_router(system.health_router)
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(config.router, prefix="/api/v1")
    app.include_router(websocket_router, prefix="/api/v1")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Do not echo config credentials or non-JSON values (NaN/Infinity) into
        # the error response; the normal validation contract needs only these.
        details = [
            {key: item[key] for key in ("loc", "msg", "type")}
            for item in error.errors()
        ]
        return JSONResponse({"detail": details}, status_code=422)

    @app.exception_handler(UpdateCheckError)
    async def update_error(request: Request, error: UpdateCheckError):
        return JSONResponse({"detail": str(error)}, status_code=502)

    @app.exception_handler(ShutdownUnavailableError)
    async def shutdown_error(request: Request, error: ShutdownUnavailableError):
        return JSONResponse({"detail": str(error)}, status_code=503)

    original_openapi = app.openapi

    def openapi_with_websocket():
        schema = original_openapi()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        websocket_schema = WebSocketMessage.model_json_schema(ref_template="#/components/schemas/{model}")
        components.update(websocket_schema.pop("$defs", {}))
        components["WebSocketMessage"] = websocket_schema
        schema["x-websocket"] = {
            "path": "/api/v1/ws", "tokenQueryParameter": "token",
            "message": {"$ref": "#/components/schemas/WebSocketMessage"},
        }
        return schema

    app.openapi = openapi_with_websocket
    return app
