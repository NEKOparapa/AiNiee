"""Backend-owned migration of writable user data; packaged assets stay read-only."""
import logging
import shutil

from Backend.core.paths import (
    _portable_mode, config_path, downloads_dir, executable_root,
    project_cache_root, user_log_dir,
)
from Backend.core.platform.platform_paths import is_windows

_log = logging.getLogger(__name__)


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
    """创建空配置，由后端 ConfigStore 填充版本化的默认值。"""
    destination = config_path()
    if destination.exists():
        return False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as writer:
            writer.write("{}\n")
        return True
    except OSError:
        return False


def _looks_like_pending_legacy_config() -> bool:
    """exe 旁还有 config.json → 用户配置还没搬到标准位置（首次升级，或上次 migrate
    transient 失败）。跳过 seed 保留下次启动重试搬迁的窗口。否则 seed 把 bundled 拷到
    dst 后，下次 _move_if_unique 看到 dst 已存在永久 refuse，用户配置永远 stranded。
    """
    return (executable_root() / "Resource" / "config.json").exists()


def migrate_config_if_needed() -> bool:
    """启动时确保 config 就位 + 把 exe 旁老数据搬到标准位置。

    分两步：
    1. legacy 用户数据每次都尝试搬（_move_if_unique idempotent），避免某次失败
       因为下次 config 已存在被永远跳过
    2. 没 config 时创建空配置，默认值由 ConfigStore 初始化。
       若检测到 stranded 状态（exe 旁 config 还在 + 有用户痕迹）则跳过 seed
    """
    if _portable_mode():
        migrated = _move_if_unique(executable_root() / "Resource" / "config.json", config_path())
        if _looks_like_pending_legacy_config() and not config_path().exists():
            raise OSError("无法迁移旧配置，请检查 Resource/config.json 的访问权限")
        if migrated:
            return True
        return _seed_default_config()
    migrated = _migrate_legacy_user_data()
    if _looks_like_pending_legacy_config() and not config_path().exists():
        raise OSError("无法迁移旧配置，请检查 Resource/config.json 的访问权限")
    if _seed_default_config():
        migrated = True
    return migrated
