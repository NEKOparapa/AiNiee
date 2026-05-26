import ctypes
from ctypes import wintypes

from ModuleFolders.Infrastructure.Platform.PlatformPaths import is_windows


APP_MUTEX_NAME = "AiNieeAppMutex"
ERROR_ALREADY_EXISTS = 183

_handle = None


def acquire_app_mutex() -> bool:
    """创建命名 mutex。返回 True 表示本进程首次持有；False 表示已有另一实例。

    Inno Setup 通过同名 AppMutex 检测应用是否运行；同时本函数返回值
    可供入口判断是否退出（非 Windows 平台始终返回 True，no-op）。
    """
    global _handle
    if _handle is not None:
        return True
    if not is_windows():
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.GetLastError.restype = wintypes.DWORD
        _handle = kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
        return kernel32.GetLastError() != ERROR_ALREADY_EXISTS
    except Exception:
        _handle = None
        return True
