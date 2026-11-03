"""Authentication and explicit DNS-rebinding protection for the MCP ASGI app."""
from __future__ import annotations

import ipaddress
import os
import re
import secrets
from typing import TYPE_CHECKING, Callable
from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

if TYPE_CHECKING:
    from mcp.server.transport_security import TransportSecuritySettings


class MCPAuthMiddleware:
    """Check every HTTP request, including requests carrying an MCP session ID.

    Mount this outside the SDK's HTTP application. FastAPI endpoint dependencies
    do not protect a mounted ASGI app, and a session ID is not authentication.
    """

    def __init__(self, app: ASGIApp, token: str | None, *, is_enabled: Callable[[], bool] | None = None):
        self.app = app
        self._token = (token or "").encode("utf-8")
        self._is_enabled = is_enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and self._token:
            headers = [value for key, value in scope.get("headers", []) if key.lower() == b"authorization"]
            authorization = headers[0] if len(headers) == 1 else b""
            scheme, separator, credentials = authorization.partition(b" ")
            matches = secrets.compare_digest(credentials, self._token)
            if len(headers) != 1 or scheme.lower() != b"bearer" or separator != b" " or not matches:
                response = JSONResponse(
                    {"detail": "MCP 访问令牌无效"}, status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        if scope["type"] == "http" and self._is_enabled is not None and not self._is_enabled():
            message = "MCP 服务已关闭，请在应用设置中启用"
            response = JSONResponse(
                {"detail": message, "error": {"code": "MCP_DISABLED", "message": message}},
                status_code=503,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


_LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z", re.IGNORECASE)


def _authority(value: str, variable: str) -> str:
    """Accept a concrete host, optionally with a port or SDK ':*' suffix."""
    message = f"{variable} 仅允许具体主机名或 IP，可附端口或 :*；不能使用域名通配符、路径或凭据"
    wildcard_port = value.endswith(":*")
    authority = value[:-2] if wildcard_port else value
    if not authority or any(character.isspace() or character in "*/?#@\\" for character in authority):
        raise ValueError(message)
    try:
        parsed = urlsplit("//" + authority)
        hostname, port = parsed.hostname, parsed.port
        if (not hostname or parsed.path or parsed.query or parsed.fragment or authority.endswith(":")
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError(message)
        # Wildcard means an unspecified port, not another suffix after one.
        if wildcard_port and port is not None:
            raise ValueError(message)
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            ascii_hostname = hostname.encode("idna").decode("ascii")
            if len(ascii_hostname) > 253 or not all(_DNS_LABEL.fullmatch(label) for label in ascii_hostname.removesuffix(".").split(".")):
                raise ValueError(message)
            authority = authority.replace(hostname, ascii_hostname)
        return authority.lower() + (":*" if wildcard_port else "")
    except (ValueError, UnicodeError):
        # Do not echo rejected values: a mistaken URL may contain credentials.
        raise ValueError(message) from None


def _origin(value: str, variable: str) -> str:
    scheme, separator, authority = value.partition("://")
    if not separator or scheme.lower() not in ("http", "https"):
        raise ValueError(f"{variable} 仅允许 http:// 或 https:// 来源，不能使用 *")
    return f"{scheme.lower()}://{_authority(authority, variable)}"


def _extend(defaults, variable, validate):
    entries = list(defaults)
    for value in os.environ.get(variable, "").split(","):
        if value.strip():
            entries.append(validate(value.strip(), variable))
    # Blank environment values never erase the safe local defaults.
    return list(dict.fromkeys(entries))


def transport_security_from_env() -> TransportSecuritySettings:
    """Keep local protection enabled; allow explicit deployment authorities.

    AINIEE_MCP_ALLOWED_HOSTS and AINIEE_MCP_ALLOWED_ORIGINS append comma-separated
    entries. They cannot disable protection or replace the defaults with '*'.
    Missing Origin headers are allowed by the official MCP transport validator.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    hosts = [entry for host in _LOCAL_HOSTS for entry in (host, f"{host}:*")]
    origins = [entry for scheme in ("http", "https") for host in _LOCAL_HOSTS
               for entry in (f"{scheme}://{host}", f"{scheme}://{host}:*")]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_extend(hosts, "AINIEE_MCP_ALLOWED_HOSTS", _authority),
        allowed_origins=_extend(origins, "AINIEE_MCP_ALLOWED_ORIGINS", _origin),
    )
