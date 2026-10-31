from Backend.core.paths import (
    cache_root,
    executable_root,
    project_cache_root,
    user_data_root,
    user_log_dir,
)
from Backend.core.platform.platform_paths import is_macos


def ensure_user_dirs() -> None:
    user_data_root().mkdir(parents=True, exist_ok=True)
    cache_root().mkdir(parents=True, exist_ok=True)
    project_cache_root().mkdir(parents=True, exist_ok=True)
    user_log_dir().mkdir(parents=True, exist_ok=True)


def prepare_working_directory():
    ensure_user_dirs()
    if not is_macos():
        return executable_root()

    # macOS 把 cwd 切到 user_data_root，避免相对路径误写到只读 .app bundle 内
    resource_link = user_data_root() / "Resource"
    if resource_link.is_symlink():
        resource_link.unlink()
    return user_data_root()
