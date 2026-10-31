"""Prepare only desktop-owned directories."""
from Frontend.core.paths import executable_root, user_data_root, user_log_dir
from Frontend.platform.platform_paths import is_macos


def ensure_user_dirs():
    user_log_dir().mkdir(parents=True, exist_ok=True)
    if is_macos():
        user_data_root().mkdir(parents=True, exist_ok=True)
    # The updater creates its download directory only when a download starts.


def prepare_working_directory():
    ensure_user_dirs()
    return user_data_root() if is_macos() else executable_root()
