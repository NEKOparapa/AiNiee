"""集中管理应用用到的文件路径。

本模块只计算路径，不创建目录、不迁移文件、不切换工作目录。
"""

import os
import platform
import sys
from pathlib import Path


APP_NAME = "AiNiee"
MACOS_APP_NAME = "AiNiee"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _is_windows() -> bool:
    return platform.system() == "Windows"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def executable_root() -> Path:
    # 打包后以可执行文件所在目录为准，避免把 PyInstaller 临时目录当成可写目录。
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return repo_root()


def writable_root() -> Path:
    return executable_root()


def resource_root() -> Path:
    override = os.environ.get("AINIEE_RESOURCE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "Resource")
        candidates.append(Path(sys._MEIPASS).parent / "Resources" / "Resource")

    app_contents = executable_root().parent
    candidates.extend(
        [
            app_contents / "Resources" / "Resource",
            executable_root() / "Resource",
            repo_root() / "Resource",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def user_data_root() -> Path:
    override = os.environ.get("AINIEE_USER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return Path.home() / "Library" / "Application Support" / MACOS_APP_NAME
    if _is_windows():
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    return repo_root()


def cache_root() -> Path:
    override = os.environ.get("AINIEE_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return Path.home() / "Library" / "Caches" / MACOS_APP_NAME
    return writable_root() / "ProjectCache"


def project_cache_root() -> Path:
    override = os.environ.get("AINIEE_PROJECT_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return user_data_root() / "ProjectCache"
    return writable_root() / "ProjectCache"


def tiktoken_cache_dir() -> Path:
    override = os.environ.get("AINIEE_TIKTOKEN_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return cache_root() / "tiktoken"
    return resource_path("Models", "tiktoken")


def bundled_tiktoken_cache_dir() -> Path:
    return resource_path("Models", "tiktoken")


def downloads_dir() -> Path:
    override = os.environ.get("AINIEE_DOWNLOADS_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if _is_macos():
        return user_data_root() / "downloads"
    return writable_root() / "downloads"


def config_path() -> Path:
    if _is_macos():
        return user_data_root() / "config.json"
    return writable_root() / "Resource" / "config.json"


def platform_preset_path() -> Path:
    return resource_path("platforms", "preset.json")


def platform_icon_path(file_name: str) -> Path:
    return resource_path("platforms", "Icon", file_name)


def prompt_path(*parts: str) -> Path:
    return resource_path("Prompt", *parts)


def regex_path(file_name: str) -> Path:
    return resource_path("Regex", file_name)


def check_regex_path() -> Path:
    return regex_path("check_regex.json")
