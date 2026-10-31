"""应用里用到的路径都放这里。

这里只管算路径，创建目录和迁移文件放到运行时流程里做。
"""

import os
import platform
import sys
from pathlib import Path


MACOS_APP_NAME = "AiNiee"
WIN_APP_NAME = "AiNiee"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _is_windows() -> bool:
    return platform.system() == "Windows"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def executable_root() -> Path:
    # 打包后用可执行文件旁边的位置，别写进 PyInstaller 临时目录。
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return repo_root()


def writable_root() -> Path:
    return executable_root()


def _win_local_app_data() -> Path:
    """Windows %LOCALAPPDATA% (C:\\Users\\<user>\\AppData\\Local)，回落 home/AppData/Local。"""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


_PORTABLE_WRITABLE_CACHE = None


def _portable_marker_present() -> bool:
    if not (getattr(sys, "frozen", False) and _is_windows()):
        return False
    return (executable_root() / "portable.txt").exists()


def _probe_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".ainiee_write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _portable_writable() -> bool:
    global _PORTABLE_WRITABLE_CACHE
    if _PORTABLE_WRITABLE_CACHE is None:
        _PORTABLE_WRITABLE_CACHE = _probe_writable(executable_root())
    return _PORTABLE_WRITABLE_CACHE


def _portable_requested() -> bool:
    flag = os.environ.get("AINIEE_PORTABLE")
    if flag == "1":
        return True
    if flag == "0":
        return False
    if not getattr(sys, "frozen", False):
        return True
    return _portable_marker_present()


def _portable_mode() -> bool:
    return _portable_requested() and _portable_writable()


def portable_fallback_active() -> bool:
    return _portable_requested() and not _portable_writable()


def packaged_resource_root(package: str, override_name: str) -> Path:
    override = os.environ.get(override_name)
    if override:
        return Path(override).expanduser().resolve()

    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / package / "resources")
        candidates.append(Path(sys._MEIPASS).parent / "Resources" / package / "resources")

    app_contents = executable_root().parent
    candidates.extend(
        [
            app_contents / "Resources" / package / "resources",
            executable_root() / package / "resources",
            repo_root() / package / "resources",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def user_data_root() -> Path:
    override = os.environ.get("AINIEE_USER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos() and not _portable_mode():
        return Path.home() / "Library" / "Application Support" / MACOS_APP_NAME
    if _is_windows() and not _portable_mode():
        return _win_local_app_data() / WIN_APP_NAME
    return writable_root()


def _has_user_data_override() -> bool:
    return bool(os.environ.get("AINIEE_USER_DATA_DIR"))


def _uses_standard_user_dir() -> bool:
    if _has_user_data_override():
        return True
    return (_is_macos() or _is_windows()) and not _portable_mode()


def user_log_dir() -> Path:
    override = os.environ.get("AINIEE_LOG_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos() and not _portable_mode():
        return Path.home() / "Library" / "Logs" / MACOS_APP_NAME
    if _is_windows() and not _portable_mode():
        return _win_local_app_data() / WIN_APP_NAME / "Logs"
    return writable_root() / "Logs" / "frontend"


def backend_log_dir() -> Path:
    """Log destination passed to the independently launched backend process."""
    override = os.environ.get("AINIEE_BACKEND_LOG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.environ.get("AINIEE_LOG_DIR"):
        return user_log_dir() / "backend"
    if (_is_macos() or _is_windows()) and not _portable_mode():
        return user_log_dir() / "backend"
    return writable_root() / "Logs" / "backend"


def downloads_dir() -> Path:
    override = os.environ.get("AINIEE_DOWNLOADS_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _uses_standard_user_dir():
        return user_data_root() / "downloads"
    return writable_root() / "downloads" / "frontend"


