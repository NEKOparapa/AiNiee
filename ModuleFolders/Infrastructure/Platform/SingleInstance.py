"""Windows 命名互斥量，让 Inno Setup CloseApplications 能检测应用是否运行中。

非 Windows 平台为 no-op。互斥量句柄进程结束时由 OS 回收，不需手动 release。
"""

import ctypes
from ctypes import wintypes

from ModuleFolders.Infrastructure.Platform.PlatformPaths import is_windows


APP_MUTEX_NAME = "AiNieeAppMutex"

_handle = None


def acquire_app_mutex() -> None:
    """创建/持有同名 mutex。同一进程多次调用幂等；失败不抛。"""
    global _handle
    if _handle is not None:
        return
    if not is_windows():
        return
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        _handle = kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
    except Exception:
        _handle = None
