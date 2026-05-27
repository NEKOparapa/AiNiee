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
    if _handle:
        return True
    if not is_windows():
        return True
    try:
        # use_last_error=True 让 ctypes 保存 GetLastError 到线程局部，
        # 不会被中间 Python 调用 clobber。
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
        last_err = ctypes.get_last_error()
        if not handle:
            # CreateMutexW 失败（如 ACCESS_DENIED），无法判断是否有其他实例，
            # 安全策略是 fail-open：让本实例继续启动，但不缓存 handle。
            return True
        if last_err == ERROR_ALREADY_EXISTS:
            # 另一实例已持有，关闭我们刚拿到的副本句柄，让对方继续唯一持有。
            kernel32.CloseHandle(handle)
            return False
        _handle = handle
        return True
    except Exception:
        _handle = None
        return True
