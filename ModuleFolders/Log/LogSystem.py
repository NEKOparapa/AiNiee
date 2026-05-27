import atexit
import faulthandler
import logging
import logging.handlers
import os
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

from ModuleFolders.Config.FilePathConfig import user_log_dir

try:
    from rich.text import Text as _RichText
except Exception:
    _RichText = None


__all__ = ("install", "redact", "get_gui_handler")


HANDLER_NAME = "ainiee_file"
LOG_FILENAME = "ainiee.log"
FAULT_LOG_FILENAME = "faulthandler.log"
CRASH_LOGGER_NAME = "AiNiee.crash"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5
RETENTION_DAYS = 30
REDACTED = "***REDACTED***"

_NOISY_THIRD_PARTY = (
    "urllib3", "httpcore", "httpx", "PIL", "matplotlib", "asyncio",
    "openai", "anthropic", "google", "boto3", "botocore",
)
_LOG_FILE_RE = re.compile(r"^ainiee\.log(\.\d+)?$")
_TAG_RE = re.compile(r"\[/?[a-zA-Z][^\]]*\]")

_API_KEY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), REDACTED),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), REDACTED),
    (re.compile(r"ya29\.[0-9A-Za-z._\-]+"), REDACTED),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{20,}", re.IGNORECASE), r"\1" + REDACTED),
)

_CONTEXT_KEY_PATTERN = re.compile(
    r"(api[_\-]?key|apikey|secret|token|authorization)"
    r"\s*[:=]\s*"
    r"['\"]?([A-Za-z0-9._\-+/=]{16,})['\"]?",
    re.IGNORECASE,
)

_EXC_FORMATTER = logging.Formatter()


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


def _strip_markup(text: str) -> str:
    if _RichText is not None:
        try:
            return _RichText.from_markup(text).plain
        except Exception:
            pass
    return _TAG_RE.sub("", text).replace("[[", "[")


def redact(text):
    """脱敏文本中常见的 API key / token / 上下文敏感字段。非 str 入参原样返回。"""
    if not isinstance(text, str):
        return text
    for pat, repl in _API_KEY_PATTERNS:
        text = pat.sub(repl, text)
    return _CONTEXT_KEY_PATTERN.sub(lambda m: f"{m.group(1)}={REDACTED}", text)


class SensitiveFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = redact(msg)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        if record.exc_info:
            exc_text = _EXC_FORMATTER.formatException(record.exc_info)
            record.exc_text = redact(exc_text)
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


_REPLAY_BUFFER_SIZE = 5000


class _GUIHandler(logging.Handler):
    """通知订阅者每条记录的格式化字符串与等级名；同时缓冲 5000 行供后来订阅者回放。"""

    def __init__(self) -> None:
        super().__init__()
        self._subscribers: list = []
        self._replay: deque = deque(maxlen=_REPLAY_BUFFER_SIZE)

    def subscribe(self, cb) -> None:
        if cb in self._subscribers:
            return
        # 回放历史给新订阅者（晚开页的用户也能看到 banner / 启动期日志）
        for line, level in list(self._replay):
            try:
                cb(line, level)
            except Exception:
                pass
        self._subscribers.append(cb)

    def unsubscribe(self, cb) -> None:
        try:
            self._subscribers.remove(cb)
        except ValueError:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            level = record.levelname
            self._replay.append((line, level))
            for cb in list(self._subscribers):
                try:
                    cb(line, level)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)


class _BroadcastStream:
    """包裹 sys.stdout/stderr：原写入照常 + 按行 flush 到 logger（再到 root → file + gui）。"""

    def __init__(self, original, logger_name: str, level: int) -> None:
        self._original = original
        self._logger = logging.getLogger(logger_name)
        self._level = level
        self._buffer = ""

    def write(self, text):
        if not text:
            return 0
        try:
            self._original.write(text)
        except Exception:
            pass
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:
                self._logger.log(self._level, line)
        return len(text)

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return self._original.isatty()
        except Exception:
            return False

    def __getattr__(self, name):
        return getattr(self._original, name)


_gui_handler: Optional["_GUIHandler"] = None


def get_gui_handler() -> "_GUIHandler":
    """懒单例 GUI handler；首次调用时挂到 root logger，配同款 formatter 与 SensitiveFilter。"""
    global _gui_handler
    if _gui_handler is not None:
        return _gui_handler
    handler = _GUIHandler()
    handler.setFormatter(
        _PlainFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    handler.addFilter(SensitiveFilter())
    logging.getLogger().addHandler(handler)
    _gui_handler = handler
    return _gui_handler


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


_fault_log_handle = None


def _close_fault_log() -> None:
    global _fault_log_handle
    if _fault_log_handle is not None:
        try:
            _fault_log_handle.close()
        except Exception:
            pass
        _fault_log_handle = None


def _enable_faulthandler(log_dir: Path) -> None:
    global _fault_log_handle
    if _fault_log_handle is not None:
        return
    try:
        _fault_log_handle = open(log_dir / FAULT_LOG_FILENAME, "a", buffering=1)
        faulthandler.enable(file=_fault_log_handle)
        atexit.register(_close_fault_log)
    except Exception:
        _fault_log_handle = None


def _apply_env_level(root: logging.Logger, handler: Optional[logging.Handler]) -> None:
    level_str = os.environ.get("AINIEE_LOG_LEVEL")
    if not level_str:
        return
    level = getattr(logging, level_str.upper(), None)
    if not isinstance(level, int):
        return
    root.setLevel(level)
    if handler is not None:
        handler.setLevel(level)
    # 同步取消 noisy 第三方 logger 的 WARNING 强制限制，方便排查 SDK 问题
    if level < logging.WARNING:
        for noisy in _NOISY_THIRD_PARTY:
            logging.getLogger(noisy).setLevel(level)


_INSTALLED = False


def install() -> Optional[Path]:
    """挂载/确认日志系统。可重入。

    返回日志文件路径；若用户日志目录不可写、或文件 handler 创建失败则返回 None。
    """
    global _INSTALLED
    try:
        log_dir = user_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        sys.stderr.write(f"[ainiee] log dir not writable, file logging disabled: {e}\n")
        return None
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
        except Exception as e:
            sys.stderr.write(f"[ainiee] file handler creation failed, file logging disabled: {e}\n")
            handler = None

    if handler is not None:
        handler.setFormatter(
            _PlainFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        # 挂在 handler 上而非 root：子 logger 的 propagate 路径只触发祖先的
        # handler filter，不触发 logger filter。mutation 跨 handler 是 by design——
        # 我们希望后续添加的任何 handler 也自动得到脱敏保护
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
    _apply_env_level(root, handler)

    # GUI handler eager 创建并挂 root，确保启动期 record（含 banner、tiktoken
    # 等通过 _BroadcastStream 转发来的 stdout）都进 replay buffer
    get_gui_handler()

    # 把 stdout/stderr 桥到 logger，让裸 print 也出现在 GUI 与 file
    if not isinstance(sys.stdout, _BroadcastStream):
        sys.stdout = _BroadcastStream(sys.stdout, "AiNiee.stdout", logging.INFO)
    if not isinstance(sys.stderr, _BroadcastStream):
        sys.stderr = _BroadcastStream(sys.stderr, "AiNiee.stderr", logging.WARNING)

    # warnings.warn 走 py.warnings logger 而非 stderr，分类更清楚也便于按级别过滤
    logging.captureWarnings(True)

    if not _INSTALLED:
        _cleanup_old_logs(log_dir, RETENTION_DAYS)
        _INSTALLED = True

    return log_path if handler is not None else None
