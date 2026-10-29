"""Serve only the optional built web frontend, never application data files."""

from pathlib import Path

from starlette.datastructures import Headers
from starlette.responses import FileResponse, JSONResponse
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocket


class FrontendFiles:
    """Share one path policy between the auth exception and the static handler.

    API paths remain reserved even if a build directory accidentally contains
    matching files. Browser HTML navigation can load the SPA's index; missing
    assets and ordinary API clients do not receive an HTML fallback.
    """

    RESERVED = frozenset(("api", "health", "openapi.json", "docs", "redoc"))
    MEDIA_TYPES = {
        ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
        ".css": "text/css", ".svg": "image/svg+xml", ".wasm": "application/wasm",
    }

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).resolve(strict=True)
        if not self.directory.is_dir():
            raise ValueError("Frontend directory must be a directory")
        index = self._inside_file(self.directory / "index.html")
        if index is None:
            raise ValueError("Frontend directory must contain its own index.html")

    def _inside_file(self, candidate: Path) -> Path | None:
        try:
            resolved = candidate.resolve(strict=True)
            if resolved.is_relative_to(self.directory) and resolved.is_file():
                return resolved
        except (OSError, RuntimeError, ValueError):
            pass
        return None

    def resolve_request(self, scope: Scope) -> Path | None:
        if scope["type"] != "http" or scope["method"] not in ("GET", "HEAD"):
            return None
        # ASGI has decoded URL escapes already. Reject leftover escapes too,
        # rather than depending on any later decoding or Windows path rules.
        path = scope.get("path", "")
        if not path.startswith("/") or any(character in path for character in ("\\", ":", "%")):
            return None
        if any(ord(character) < 32 for character in path) or "//" in path:
            return None
        parts = path.strip("/").split("/") if path != "/" else []
        if any(part.startswith(".") or not part for part in parts):
            return None
        if parts and parts[0].lower() in self.RESERVED:
            return None
        candidate = self.directory.joinpath(*parts)
        # Resolve first, including a nonexistent leaf's parents: a symlinked
        # directory outside the bundle must not become an HTML fallback.
        try:
            if not candidate.resolve().is_relative_to(self.directory):
                return None
        except (OSError, RuntimeError, ValueError):
            return None
        file = self._inside_file(candidate)
        if file is not None:
            return file
        if not parts:
            return self._inside_file(self.directory / "index.html")
        accept = Headers(scope=scope).get("accept", "").lower()
        if "text/html" in accept and not candidate.suffix and parts[0].lower() != "assets":
            return self._inside_file(self.directory / "index.html")
        return None

    def is_public(self, scope: Scope) -> bool:
        return self.resolve_request(scope) is not None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await WebSocket(scope, receive, send).close(code=1008)
            return
        if scope["method"] not in ("GET", "HEAD"):
            await JSONResponse({"detail": "Method Not Allowed"}, status_code=405,
                               headers={"Allow": "GET, HEAD"})(scope, receive, send)
            return
        file = self.resolve_request(scope)
        if file is None:
            await JSONResponse({"detail": "Not Found"}, status_code=404)(scope, receive, send)
            return
        await FileResponse(
            file, media_type=self.MEDIA_TYPES.get(file.suffix.lower()),
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                     "Referrer-Policy": "no-referrer"},
        )(scope, receive, send)
