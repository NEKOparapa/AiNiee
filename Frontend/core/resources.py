"""Read-only desktop assets; business templates and models belong to the backend."""
from pathlib import Path

from Frontend.core.paths import packaged_resource_root


def frontend_resource_root() -> Path:
    return packaged_resource_root("Frontend", "AINIEE_FRONTEND_RESOURCE_DIR")


def frontend_resource_path(*parts: str) -> Path:
    return frontend_resource_root().joinpath(*parts)


def platform_icon_path(file_name: str) -> Path:
    return frontend_resource_path("platform_icons", file_name)
