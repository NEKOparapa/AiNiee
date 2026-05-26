"""启动期日志兜底：仅依赖 stdlib，必须在任何第三方 import 之前调用。

覆盖以下黑屏场景：
  - 第三方包 import 失败（PyQt5 / rich / msgspec 等没装齐时最常见）
  - Qt 初始化崩溃在主窗口之前
  - C 层崩溃 / segfault（PyInstaller --windowed 下 stderr=None 完全无痕迹）

设计要点：
  - 与 FileBackend.HANDLER_NAME 同名挂在 root logger 上，后续 init_file_logging
    检测到不会重复装，而是把 formatter/filter 升级上来。
  - excepthook 标记 _is_bootstrap 属性，install_crash_hooks 见之直接接
    sys.__excepthook__，避免链式双写。
  - 所有失败 swallow，bootstrap 自身不能反过来阻碍启动。
"""

import faulthandler
import logging
import logging.handlers
import os
import platform
import sys
from pathlib import Path


HANDLER_NAME = "ainiee_file"
LOG_FILENAME = "ainiee.log"
FAULT_LOG_FILENAME = "faulthandler.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5
MACOS_APP_NAME = "AiNiee"

_INSTALLED = False
_fault_log_handle = None


def _bootstrap_log_dir() -> Path:
    """与 FilePathConfig.user_log_dir() 行为一致，但仅用 stdlib。"""
    override = os.environ.get("AINIEE_LOG_DIR")
    if override:
        d = Path(override).expanduser().resolve()
    elif platform.system() == "Darwin":
        d = Path.home() / "Library" / "Logs" / MACOS_APP_NAME
    else:
        if getattr(sys, "frozen", False):
            d = Path(sys.executable).resolve().parent / "Logs"
        else:
            # 源码运行：本模块在 ModuleFolders/Log/，仓库根 = parents[2]
            d = Path(__file__).resolve().parents[2] / "Logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _attach_file_handler(log_dir: Path) -> None:
    root = logging.getLogger()
    for existing in root.handlers:
        if getattr(existing, "name", "") == HANDLER_NAME:
            return
    handler = logging.handlers.RotatingFileHandler(
        log_dir / LOG_FILENAME,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    handler.set_name(HANDLER_NAME)
    current = root.level if root.level != logging.NOTSET else logging.INFO
    root.setLevel(min(current, logging.INFO))
    root.addHandler(handler)


def _attach_excepthook() -> None:
    original = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        try:
            logging.getLogger("AiNiee.bootstrap").critical(
                "Uncaught exception during startup",
                exc_info=(exc_type, exc_value, exc_tb),
            )
        except Exception:
            pass
        if original is not None:
            original(exc_type, exc_value, exc_tb)

    hook._is_bootstrap = True  # type: ignore[attr-defined]
    sys.excepthook = hook


def _enable_faulthandler(log_dir: Path) -> None:
    global _fault_log_handle
    if _fault_log_handle is not None:
        return
    try:
        _fault_log_handle = open(log_dir / FAULT_LOG_FILENAME, "a", buffering=1)
        faulthandler.enable(file=_fault_log_handle)
    except Exception:
        _fault_log_handle = None


def install() -> None:
    """启动最早期调用一次即可。幂等，所有失败 swallow。"""
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        log_dir = _bootstrap_log_dir()
        _attach_file_handler(log_dir)
        _attach_excepthook()
        _enable_faulthandler(log_dir)
    except Exception:
        pass
    _INSTALLED = True
