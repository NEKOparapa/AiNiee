"""统一日志系统。

单点入口 install()，AiNiee.py 顶最早期调用一次即可：
- 在用户日志目录挂 RotatingFileHandler（5MB×5，启动时清理 30 天以上旧文件）
- rich 标记剥离（rich 缺失时回落到正则）
- 常见 API key 形态 + 上下文兜底脱敏（同时覆盖 record.msg 与 exc_info）
- sys.excepthook + threading.excepthook 落盘未捕获异常
- faulthandler 写单独文件抓 C 层崩溃
- stdout/stderr 为 None 时回填 devnull（PyInstaller --windowed 兜底）

仅依赖 stdlib + 可选 rich；任何失败 swallow，不阻碍启动。
"""

import faulthandler
import logging
import logging.handlers
import os
import re
import sys
import threading
import time
from pathlib import Path

from ModuleFolders.Config.FilePathConfig import user_log_dir


__all__ = ("install", "SensitiveFilter")


HANDLER_NAME = "ainiee_file"
LOG_FILENAME = "ainiee.log"
FAULT_LOG_FILENAME = "faulthandler.log"
CRASH_LOGGER_NAME = "AiNiee.crash"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5
RETENTION_DAYS = 30
REDACTED = "***REDACTED***"

_NOISY_THIRD_PARTY = ("urllib3", "httpcore", "httpx", "PIL", "matplotlib", "asyncio")


# === 旧日志清理 ===
_LOG_FILE_RE = re.compile(r"^ainiee\.log(\.\d+)?$")


def _cleanup_old_logs(directory: Path, retention_days: int) -> None:
    if not directory.exists():
        return
    cutoff = time.time() - retention_days * 86400
    for path in directory.iterdir():
        if not _LOG_FILE_RE.match(path.name):
            continue
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


# === rich 标记剥离（rich 可选） ===
_TAG_RE = re.compile(r"\[/?[a-zA-Z][^\]]*\]")


def _strip_markup(text: str) -> str:
    try:
        from rich.text import Text
        return Text.from_markup(text).plain
    except Exception:
        return _TAG_RE.sub("", text).replace("[[", "[")


# === 脱敏 ===
_API_KEY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"ya29\.[0-9A-Za-z._\-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE),
)

_CONTEXT_KEY_PATTERN = re.compile(
    r"(api[_\-]?key|apikey|secret|token|authorization)"
    r"\s*[:=]\s*"
    r"['\"]?([A-Za-z0-9._\-+/=]{16,})['\"]?",
    re.IGNORECASE,
)


def _redact(text: str) -> str:
    for pat in _API_KEY_PATTERNS:
        text = pat.sub(REDACTED, text)
    return _CONTEXT_KEY_PATTERN.sub(lambda m: f"{m.group(1)}={REDACTED}", text)


class SensitiveFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = _redact(msg)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        if record.exc_info:
            exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_text = _redact(exc_text)
        return True


class _PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args
        try:
            text = record.getMessage()
            record.msg = _strip_markup(text)
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


# === 崩溃捕获 ===
_DEVNULL = None


def _ensure_std_streams() -> None:
    global _DEVNULL
    if sys.stdout is not None and sys.stderr is not None:
        return
    if _DEVNULL is None:
        _DEVNULL = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = _DEVNULL
    if sys.stderr is None:
        sys.stderr = _DEVNULL


_original_excepthook = None
_original_thread_excepthook = None


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    try:
        logging.getLogger(CRASH_LOGGER_NAME).critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_tb)
        )
    except Exception:
        pass
    if _original_excepthook is not None:
        _original_excepthook(exc_type, exc_value, exc_tb)


def _thread_excepthook(args) -> None:
    thread_name = getattr(args.thread, "name", "<unknown>") if args.thread else "<unknown>"
    try:
        logging.getLogger(CRASH_LOGGER_NAME).critical(
            f"Uncaught exception in thread {thread_name}",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
    except Exception:
        pass
    if _original_thread_excepthook is not None:
        _original_thread_excepthook(args)


def _install_crash_hooks() -> None:
    global _original_excepthook, _original_thread_excepthook
    if _original_excepthook is not None:
        return
    _ensure_std_streams()
    _original_excepthook = sys.excepthook
    sys.excepthook = _excepthook
    _original_thread_excepthook = threading.excepthook
    threading.excepthook = _thread_excepthook


# === faulthandler ===
_fault_log_handle = None


def _enable_faulthandler(log_dir: Path) -> None:
    global _fault_log_handle
    if _fault_log_handle is not None:
        return
    try:
        _fault_log_handle = open(log_dir / FAULT_LOG_FILENAME, "a", buffering=1)
        faulthandler.enable(file=_fault_log_handle)
    except Exception:
        _fault_log_handle = None


# === 单点入口 ===
_INSTALLED = False


def install() -> Path:
    """挂载/确认日志系统。可重入；失败 swallow。返回日志文件路径。"""
    global _INSTALLED
    try:
        log_dir = user_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return Path(os.devnull)
    log_path = log_dir / LOG_FILENAME

    root = logging.getLogger()
    handler = next(
        (h for h in root.handlers if getattr(h, "name", "") == HANDLER_NAME),
        None,
    )
    if handler is None:
        try:
            handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
                delay=True,
            )
            handler.set_name(HANDLER_NAME)
            root.addHandler(handler)
        except Exception:
            handler = None

    if handler is not None:
        handler.setFormatter(
            _PlainFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        if not any(isinstance(f, SensitiveFilter) for f in handler.filters):
            handler.addFilter(SensitiveFilter())

    current = root.level if root.level != logging.NOTSET else logging.INFO
    root.setLevel(min(current, logging.INFO))

    for noisy in _NOISY_THIRD_PARTY:
        lg = logging.getLogger(noisy)
        if lg.level == logging.NOTSET or lg.level < logging.WARNING:
            lg.setLevel(logging.WARNING)

    _install_crash_hooks()
    _enable_faulthandler(log_dir)

    if not _INSTALLED:
        _cleanup_old_logs(log_dir, RETENTION_DAYS)
        _INSTALLED = True

    return log_path
