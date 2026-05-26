import ctypes
from ctypes import wintypes

from ModuleFolders.Infrastructure.Platform.PlatformPaths import is_windows


APP_MUTEX_NAME = "AiNieeAppMutex"

_handle = None


def acquire_app_mutex() -> None:
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
