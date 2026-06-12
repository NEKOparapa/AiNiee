import logging
import shutil

from ModuleFolders.Config.FilePathConfig import (
    _portable_mode,
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


_log = logging.getLogger(__name__)


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
    """src 存在 → 搬到 dst。

    dst 已存在且为空（典型场景：ensure_user_dirs 先 mkdir 出来的空目录）→
    先 rmdir 再 move；dst 已存在且非空 → 保留 dst 不覆盖。
    失败 swallow 但记录 warning，便于排查。
    """
    if not src.exists():
        return False
    src_resolved = src.resolve()
    dst_resolved = dst.resolve() if dst.exists() else dst
    if src_resolved == dst_resolved:
        return False
    if dst.exists():
        try:
            if dst.is_dir() and not any(dst.iterdir()):
                dst.rmdir()
            else:
                return False
        except OSError:
            return False
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True
    except Exception:
        _log.warning("legacy migration failed: %s -> %s", src, dst, exc_info=True)
        return False


def _migrate_legacy_user_data() -> bool:
    """把老版本留在 exe 旁的 user data 搬到标准位置。idempotent，每次启动可安全调用。

    exe 旁的 Resource/config.json 是老版本写的用户配置（打包产物不在 exe 旁放 config），
    无条件搬到标准位置——只配置过 API key、没产生 ProjectCache/downloads 痕迹的用户
    升级后也不会丢配置。_move_if_unique 不覆盖标准位置已存在的 config，幂等安全。
    """
    if not (is_macos() or is_windows()):
        return False
    exe_dir = executable_root()
    legacy_pairs = [
        (exe_dir / "ProjectCache", project_cache_root()),
        (exe_dir / "downloads", downloads_dir()),
    ]
    migrated = False
    for src, dst in legacy_pairs:
        if _move_if_unique(src, dst):
            migrated = True
    # Windows 老版本把 Logs 放 exe 旁；新 user_log_dir() 已经在写 ainiee.log，
    # 不能整体替换，归档到 user_log_dir()/legacy/ 保留排错素材
    if is_windows():
        legacy_logs = exe_dir / "Logs"
        if _move_if_unique(legacy_logs, user_log_dir() / "legacy"):
            migrated = True
    # exe 旁的 config.json 只要存在就是用户配置，无条件搬到标准位置（见函数 docstring）。
    legacy_config = exe_dir / "Resource" / "config.json"
    if _move_if_unique(legacy_config, config_path()):
        migrated = True
    return migrated


def _seed_default_config() -> bool:
    """新位置没 config 时，从打包 Resource/config.json 复制一份默认。COPY 保留模板。"""
    destination = config_path()
    if destination.exists():
        return False
    source = resource_path("config.json")
    if not source.exists():
        return False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return True
    except OSError:
        return False


def _looks_like_pending_legacy_config() -> bool:
    """exe 旁还有 config.json → 用户配置还没搬到标准位置（首次升级，或上次 migrate
    transient 失败）。跳过 seed 保留下次启动重试搬迁的窗口。否则 seed 把 bundled 拷到
    dst 后，下次 _move_if_unique 看到 dst 已存在永久 refuse，用户配置永远 stranded。
    """
    if not (is_macos() or is_windows()):
        return False
    return (executable_root() / "Resource" / "config.json").exists()


def migrate_config_if_needed() -> bool:
    """启动时确保 config 就位 + 把 exe 旁老数据搬到标准位置。

    分两步：
    1. legacy 用户数据每次都尝试搬（_move_if_unique idempotent），避免某次失败
       因为下次 config 已存在被永远跳过
    2. 没 config 时从 bundled 复制一份默认（COPY，不 MOVE），保留 install 内模板。
       若检测到 stranded 状态（exe 旁 config 还在 + 有用户痕迹）则跳过 seed
    """
    if _portable_mode():
        return _seed_default_config()
    migrated = _migrate_legacy_user_data()
    if _looks_like_pending_legacy_config():
        return migrated
    if _seed_default_config():
        migrated = True
    return migrated
