"""Backend abstraction: how the MCP triggers/observes AiNiee.

Phase A ships HttpBackend (talks to a running AiNiee over HTTP).
Phase B will add InProcessBackend (no GUI). `get_backend()` is the only switch point.
"""
from __future__ import annotations

import os

from .base import AiNieeBackend


def get_backend() -> AiNieeBackend:
    kind = os.environ.get("AINIEE_MCP_BACKEND", "http").lower()
    if kind == "http":
        from .http_backend import HttpBackend

        return HttpBackend()
    # Phase B:
    # if kind == "inprocess":
    #     from .inprocess_backend import InProcessBackend
    #     return InProcessBackend()
    raise ValueError(f"Unknown AINIEE_MCP_BACKEND={kind!r} (expected 'http')")
