import shutil

from ModuleFolders.Config.FilePathConfig import (
    cache_root,
    config_path,
    downloads_dir,
    executable_root,
    project_cache_root,
    resource_path,
    user_data_root,
    user_log_dir,
)
from ModuleFolders.Infrastructure.Platform.PlatformPaths import is_macos, is_windows


def ensure_user_dirs() -> None:
    user_data_root().mkdir(parents=True, exist_ok=True)
    cache_root().mkdir(parents=True, exist_ok=True)
    project_cache_root().mkdir(parents=True, exist_ok=True)
    downloads_dir().mkdir(parents=True, exist_ok=True)
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


def _move_if_unique(src, dst) -> bool:
    """source 存在且不等于 destination 且 destination 不存在时 move 过去。失败 swallow。"""
    if not src.exists():
        return False
    src_resolved = src.resolve()
    dst_resolved = dst.resolve() if dst.exists() else dst
    if src_resolved == dst_resolved:
        return False
    if dst.exists():
        return False
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True
    except Exception:
        return False


def migrate_config_if_needed() -> bool:
    """首次启动时把配置就位。同时尝试从 exe 旁的老位置迁移用户数据。

    顺序：
    1. 若新位置已有 config，跳过
    2. macOS / Windows：尝试从 exe 旁老位置（早期版本的存放位置）move 整套用户数据
    3. 仍无 config：从打包内置的 Resource/config.json 复制一份作默认
    """
    destination = config_path()
    if destination.exists():
        return False

    migrated = False
    # macOS / Windows 上：早期版本可能把配置/缓存/下载放在 exe 旁，搬到新位置
    if is_macos() or is_windows():
        exe_dir = executable_root()
        legacy_pairs = [
            (exe_dir / "Resource" / "config.json", destination),
            (exe_dir / "ProjectCache", project_cache_root()),
            (exe_dir / "downloads", downloads_dir()),
        ]
        for src, dst in legacy_pairs:
            if _move_if_unique(src, dst):
                migrated = True

    if destination.exists():
        return migrated

    # 内置默认配置兜底（首次干净安装）
    if not (is_macos() or is_windows()):
        return migrated

    source = resource_path("config.json")
    if not source.exists():
        return migrated

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True
