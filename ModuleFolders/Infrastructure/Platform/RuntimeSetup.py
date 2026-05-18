import shutil

from ModuleFolders.Config.FilePathConfig import (
    cache_root,
    config_path,
    downloads_dir,
    executable_root,
    project_cache_root,
    resource_path,
    user_data_root,
)
from ModuleFolders.Infrastructure.Platform.PlatformPaths import is_macos


def ensure_user_dirs() -> None:
    user_data_root().mkdir(parents=True, exist_ok=True)
    cache_root().mkdir(parents=True, exist_ok=True)
    project_cache_root().mkdir(parents=True, exist_ok=True)
    downloads_dir().mkdir(parents=True, exist_ok=True)


def prepare_working_directory():
    if not is_macos():
        return executable_root()

    # 运行时准备只放在入口流程里，路径定义统一留在 FilePathConfig。
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
