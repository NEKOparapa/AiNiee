"""进程状态和版本信息，不依赖服务框架或界面。"""

import json
import logging
from collections.abc import Callable

from ModuleFolders.Config.FilePathConfig import resource_path


class ShutdownUnavailableError(RuntimeError):
    """调用方未提供服务进程的关闭回调。"""


class SystemService:
    def __init__(self, shutdown_callback: Callable[[], None] | None = None) -> None:
        self._shutdown_callback = shutdown_callback

    def get_health(self) -> dict:
        return {"status": "ok"}

    def get_version(self) -> dict:
        default_version = "Unknown Version"
        path = resource_path("Version", "version.json")
        try:
            with path.open(encoding="utf-8") as source:
                data = json.load(source)
            version = data.get("version") if isinstance(data, dict) else None
            if not isinstance(version, str) or not version:
                version = default_version
        except (OSError, ValueError):
            logging.getLogger(__name__).warning("读取版本文件失败：%s", path)
            version = default_version
        return {"version": version}

    def request_shutdown(self) -> dict:
        if self._shutdown_callback is None:
            raise ShutdownUnavailableError("Server shutdown callback is not configured")
        self._shutdown_callback()
        return {"status": "shutting_down"}
