"""Error types surfaced to the MCP client with an actionable `user_message`."""
from __future__ import annotations

from typing import Iterable


class AiNieeError(Exception):
    """Base error. `user_message` is the actionable text shown to the AI / user."""

    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


class AiNieeUnavailable(AiNieeError):
    def __init__(self, base_url: str):
        super().__init__(
            f"cannot reach AiNiee at {base_url}",
            f"AiNiee 未在 {base_url} 监听。请打开 AiNiee，在「设置」中启用 HTTP 监听服务后重启，再重试。",
        )


class AiNieeBusy(AiNieeError):
    def __init__(self, detail: str = ""):
        super().__init__(
            f"AiNiee is busy: {detail}".strip(),
            "AiNiee 正在执行任务（翻译中 / 停止中）。请先停止当前任务或等待其完成后再试。",
        )


class NoProjectLoaded(AiNieeError):
    def __init__(self):
        super().__init__(
            "no project loaded",
            "AiNiee 当前没有已加载的项目。请先用 ainiee_load_project 加载项目，或在 AiNiee 中打开一个项目。",
        )


class ValidationError(AiNieeError):
    def __init__(self, message: str, allowed: Iterable[str] | None = None):
        if allowed is not None:
            message = f"{message} (allowed: {sorted(allowed)})"
        super().__init__(message, message)
