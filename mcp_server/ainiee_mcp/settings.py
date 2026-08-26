"""Environment-driven settings (read at call time so tests can monkeypatch)."""
from __future__ import annotations

import os

DEFAULT_BASE_URL = "http://127.0.0.1:3388"


def base_url() -> str:
    return os.environ.get("AINIEE_HTTP_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def http_timeout() -> float:
    try:
        return float(os.environ.get("AINIEE_HTTP_TIMEOUT", "30"))
    except ValueError:
        return 30.0


def backend_kind() -> str:
    return os.environ.get("AINIEE_MCP_BACKEND", "http").lower()
