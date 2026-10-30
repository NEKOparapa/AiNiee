"""Authentication applies before routing, including unknown HTTP/WS paths."""

import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, WebSocket, WebSocketException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.datastructures import Headers, QueryParams
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from ModuleFolders.Application.ConfigService import ConfigService
from ModuleFolders.Application.PlatformService import PlatformService
from ModuleFolders.Application.ProjectService import ProjectService
from ModuleFolders.Application.SystemService import SystemService
from ModuleFolders.Application.TaskService import TaskService
from ModuleFolders.Application.UpdateService import UpdateService
from ModuleFolders.Application.ItemService import ItemService
from ModuleFolders.Application.CheckService import CheckService
from ModuleFolders.Application.ExportService import ExportService
from ModuleFolders.Application.TableService import TableService
from ModuleFolders.Application.PromptService import PromptService
from ModuleFolders.Application.AnalysisService import AnalysisService


bearer = HTTPBearer(auto_error=False, scheme_name="BearerToken")


def token_matches(candidate: str | None, expected: str) -> bool:
    return candidate is not None and secrets.compare_digest(
        candidate.encode("utf-8"), expected.encode("utf-8")
    )


def _http_token(headers: Headers) -> str | None:
    values = headers.getlist("authorization")
    if len(values) != 1:
        return None
    scheme, _, value = values[0].partition(" ")
    return value if scheme.lower() == "bearer" else None


def _websocket_token(scope: Scope) -> str | None:
    values = QueryParams(scope.get("query_string", b"")).getlist("token")
    return values[0] if len(values) == 1 else None


class TokenAuthMiddleware:
    def __init__(self, app: ASGIApp, *, token: str, allowed_origins: tuple[str, ...],
                 public_http: Callable[[Scope], bool] | None = None):
        self.app = app
        self.token = token
        self.allowed_origins = allowed_origins
        self.public_http = public_http

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")
        origin_allowed = origin is None or origin in self.allowed_origins
        if scope["type"] == "websocket":
            if not origin_allowed or not token_matches(_websocket_token(scope), self.token):
                await WebSocket(scope, receive, send).close(code=1008)
                return
        else:
            if not origin_allowed:
                await JSONResponse({"detail": "Origin is not allowed"}, status_code=403)(scope, receive, send)
                return
            preflight = (
                scope["method"] == "OPTIONS"
                and origin in self.allowed_origins
                and "access-control-request-method" in headers
            )
            health = scope["method"] == "GET" and scope["path"] == "/health"
            public_file = self.public_http is not None and self.public_http(scope)
            if not health and not preflight and not public_file and not token_matches(_http_token(headers), self.token):
                response_headers = {"WWW-Authenticate": "Bearer"}
                if origin is not None:
                    response_headers.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
                await JSONResponse(
                    {"detail": "Invalid or missing token"}, status_code=401, headers=response_headers
                )(scope, receive, send)
                return
        await self.app(scope, receive, send)


def require_http_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    if credentials is None or not token_matches(credentials.credentials, request.app.state.token):
        raise HTTPException(401, "Invalid or missing token", headers={"WWW-Authenticate": "Bearer"})


async def require_websocket_token(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if (
        origin is not None and origin not in websocket.app.state.allowed_origins
    ) or not token_matches(_websocket_token(websocket.scope), websocket.app.state.token):
        raise WebSocketException(code=1008)


def get_config_service(request: Request) -> ConfigService:
    return request.app.state.config_service


def get_system_service(request: Request) -> SystemService:
    return request.app.state.system_service


def get_update_service(request: Request) -> UpdateService:
    return request.app.state.update_service


def get_task_service(request: Request) -> TaskService:
    return request.app.state.task_service


def get_table_service() -> TableService:
    return TableService()


def get_prompt_service() -> PromptService:
    return PromptService()


def get_analysis_service(request: Request) -> AnalysisService:
    return AnalysisService(request.app.state.runtime.cache_manager)


def get_item_service(request: Request) -> ItemService:
    return ItemService(request.app.state.runtime.cache_manager)


def get_check_service(request: Request) -> CheckService:
    return CheckService(request.app.state.runtime.cache_manager)


def get_export_service(request: Request) -> ExportService:
    runtime = request.app.state.runtime
    return ExportService(runtime.cache_manager, runtime.file_writer, runtime.task_executor)


def get_platform_service(request: Request) -> PlatformService:
    return PlatformService()


def get_project_service(request: Request) -> ProjectService:
    runtime = request.app.state.runtime
    return ProjectService(runtime.cache_manager, runtime.file_reader)
