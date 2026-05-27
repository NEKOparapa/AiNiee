import logging
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


def _has_files(path) -> bool:
    """目录存在且非空。ensure_user_dirs 创出的空目录不算"用户痕迹"。"""
    try:
        return path.is_dir() and any(path.iterdir())
    except OSError:
        return False


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

    config.json 不在 legacy_pairs：bundled 默认走 _seed_default_config 复制保留模板；
    若 exe 旁同时存在 ProjectCache/downloads 等用户痕迹，那个 config 才按用户配置搬走。
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
    # exe 旁有"用户痕迹"（非空 ProjectCache/downloads）时，把 exe 旁 config 当用户配置搬走。
    # 用 _has_files 而非 .exists()——ensure_user_dirs 先建出的空目录不算痕迹
    if migrated or _has_files(project_cache_root()) or _has_files(downloads_dir()):
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


def migrate_config_if_needed() -> bool:
    """启动时确保 config 就位 + 把 exe 旁老数据搬到标准位置。

    分两步：
    1. legacy 用户数据每次都尝试搬（_move_if_unique idempotent），避免某次失败
       因为下次 config 已存在被永远跳过
    2. 没 config 时从 bundled 复制一份默认（COPY，不 MOVE），保留 install 内模板
    """
    migrated = _migrate_legacy_user_data()
    if _seed_default_config():
        migrated = True
    return migrated
