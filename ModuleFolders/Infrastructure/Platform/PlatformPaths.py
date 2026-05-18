import platform

from ModuleFolders.Config.FilePathConfig import MACOS_APP_NAME


UPSTREAM_RELEASE_API_URL = "https://api.github.com/repos/NEKOparapa/AiNiee/releases/latest"
MACOS_RELEASE_API_URL = UPSTREAM_RELEASE_API_URL


def is_macos() -> bool:
    return platform.system() == "Darwin"


def is_windows() -> bool:
    return platform.system() == "Windows"


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
