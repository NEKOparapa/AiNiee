import os
import platform
import shutil
import sys
from pathlib import Path


APP_NAME = "AiNiee"
MACOS_APP_NAME = "AiNiee"
UPSTREAM_RELEASE_API_URL = "https://api.github.com/repos/NEKOparapa/AiNiee/releases/latest"
MACOS_RELEASE_API_URL = UPSTREAM_RELEASE_API_URL


def is_macos() -> bool:
    return platform.system() == "Darwin"


def is_windows() -> bool:
    return platform.system() == "Windows"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def executable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return repo_root()


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


def stev_extraction_root() -> Path:
    override = os.environ.get("AINIEE_STEV_EXTRACTION_DIR")
    if override:
        return Path(override).expanduser().resolve()

    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "StevExtraction")

    app_contents = executable_root().parent
    candidates.extend(
        [
            app_contents / "Resources" / "StevExtraction",
            executable_root() / "StevExtraction",
            repo_root() / "StevExtraction",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def stev_extraction_path(*parts: str) -> Path:
    return stev_extraction_root().joinpath(*parts)


def stev_extraction_config_path() -> Path:
    return stev_extraction_path("config.yaml")


def release_api_url() -> str:
    if is_macos():
        return MACOS_RELEASE_API_URL
    return UPSTREAM_RELEASE_API_URL


def ui_font_family() -> str:
    if is_macos():
        return ".AppleSystemUIFont"
    return "Microsoft YaHei"


def monospace_font_family() -> str:
    if is_macos():
        return "Menlo"
    return "Consolas"


def user_data_root() -> Path:
    override = os.environ.get("AINIEE_USER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if is_macos():
        return Path.home() / "Library" / "Application Support" / MACOS_APP_NAME
    if is_windows():
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
    return repo_root()


def cache_root() -> Path:
    override = os.environ.get("AINIEE_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if is_macos():
        return Path.home() / "Library" / "Caches" / MACOS_APP_NAME
    return repo_root() / "ProjectCache"


def project_cache_root() -> Path:
    override = os.environ.get("AINIEE_PROJECT_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if is_macos():
        return user_data_root() / "ProjectCache"
    return repo_root() / "ProjectCache"


def tiktoken_cache_dir() -> Path:
    override = os.environ.get("AINIEE_TIKTOKEN_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if is_macos():
        return cache_root() / "tiktoken"
    return resource_path("Models", "tiktoken")


def downloads_dir() -> Path:
    override = os.environ.get("AINIEE_DOWNLOADS_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if is_macos():
        return user_data_root() / "downloads"
    return repo_root() / "downloads"


def config_path() -> Path:
    if is_macos():
        return user_data_root() / "config.json"
    return resource_path("config.json")


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


def ensure_user_dirs() -> None:
    user_data_root().mkdir(parents=True, exist_ok=True)
    cache_root().mkdir(parents=True, exist_ok=True)
    project_cache_root().mkdir(parents=True, exist_ok=True)
    downloads_dir().mkdir(parents=True, exist_ok=True)


def prepare_working_directory() -> Path:
    if not is_macos():
        return executable_root()

    ensure_user_dirs()
    resource_link = user_data_root() / "Resource"
    if resource_link.is_symlink():
        resource_link.unlink()
    return user_data_root()


def migrate_config_if_needed() -> bool:
    if not is_macos():
        return False

    destination = config_path()
    if destination.exists():
        return False

    source = resource_path("config.json")
    if not source.exists():
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True
