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

__all__ = ("install", "redact", "get_gui_handler")


HANDLER_NAME = "ainiee_file"
LOG_FILENAME = "ainiee.log"
FAULT_LOG_FILENAME = "faulthandler.log"
CRASH_LOGGER_NAME = "AiNiee.crash"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5
RETENTION_DAYS = 30
FAULT_MAX_BYTES = 1 * 1024 * 1024
REDACTED = "***REDACTED***"

_NOISY_THIRD_PARTY = (
    "urllib3", "httpcore", "httpx", "PIL", "matplotlib", "asyncio",
    "openai", "anthropic", "google", "boto3", "botocore",
)
_LOG_FILE_RE = re.compile(r"^ainiee\.log(\.\d+)?$")
# 终端 ANSI 转义：CSI（SGR/光标 等）+ OSC（窗口标题、OSC 8 超链接等，BEL 或 ST 结束）
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]{0,1024}(?:\x07|\x1b\\)")

_API_KEY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), REDACTED),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), REDACTED),
    (re.compile(r"ya29\.[0-9A-Za-z._\-]+"), REDACTED),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{20,}", re.IGNORECASE), r"\1" + REDACTED),
)

_CONTEXT_KEY_PATTERN = re.compile(
    r"(api[_\-]?key|apikey|access[_\-]?key|secret[_\-]?access[_\-]?key|secret[_\-]?key|secret|token|authorization|password|passwd|pwd)"
    r"(['\"]?\s*[:=]\s*['\"]?)"
    r"[^'\"\s,;&\])}]+(?:,[^'\"\s,;&\])}]+)*"
    r"(['\"]?)",
    re.IGNORECASE,
)

_AUTH_VALUE_PATTERN = re.compile(
    r"((?:proxy-)?authorization)(['\"]?\s*[:=]\s*)\S[^\r\n,;&}\])'\"]*",
    re.IGNORECASE,
)

_URL_CRED_PATTERN = re.compile(r"([a-z][a-z0-9+.\-]{0,15}://)[^/\s@]+@", re.IGNORECASE)

_QUOTED_SECRET_PATTERN = re.compile(
    r"(api[_\-]?key|apikey|access[_\-]?key|secret[_\-]?access[_\-]?key|secret[_\-]?key|secret|token|authorization|password|passwd|pwd)"
    r"(\s*[:=]\s*)(['\"])[^'\"]*\3",
    re.IGNORECASE,
)

_EXC_FORMATTER = logging.Formatter()

# 线程局部嵌套深度：LogMixin 调 rich.print 前 +1，退出 -1。
# _BroadcastStream 看到 depth > 0 就跳过 logger.log，避免 LogMixin 双写。
# 用 counter 而非 bool 以正确处理 reentrant 调用（嵌套 rich.print 时内层 finally
# 不会过早清零外层的标记）。
_in_log_mixin = threading.local()


def _in_log_mixin_active() -> bool:
    return getattr(_in_log_mixin, "depth", 0) > 0


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
    return _ANSI_RE.sub("", text)


def redact(text):
    """脱敏文本中常见的 API key / token / 上下文敏感字段。非 str 入参原样返回。"""
    if not isinstance(text, str):
        return text
    for pat, repl in _API_KEY_PATTERNS:
        text = pat.sub(repl, text)
    text = _AUTH_VALUE_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    text = _URL_CRED_PATTERN.sub(lambda m: f"{m.group(1)}{REDACTED}@", text)
    text = _QUOTED_SECRET_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{REDACTED}{m.group(3)}", text)
    return _CONTEXT_KEY_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}{m.group(3)}", text)


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
        gui_text = getattr(record, "ainiee_gui_text", None)
        if isinstance(gui_text, str):
            record.ainiee_gui_text = redact(gui_text)
        gui_rows = getattr(record, "ainiee_gui_rows", None)
        if isinstance(gui_rows, list):
            record.ainiee_gui_rows = [
                [redact(cell) if isinstance(cell, str) else cell for cell in row]
                if isinstance(row, list) else row
                for row in gui_rows
            ]
        if record.exc_info:
            exc_text = _EXC_FORMATTER.formatException(record.exc_info)
            record.exc_text = redact(exc_text)
        return True


class _PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args
        try:
            plain = getattr(record, "_ainiee_plain", None)
            if plain is None:
                plain = _strip_markup(record.getMessage())
                record._ainiee_plain = plain
            record.msg = plain
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


class _ConsoleFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(message)s")

    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args
        try:
            gui_text = getattr(record, "ainiee_gui_text", None)
            if isinstance(gui_text, str):
                plain = _strip_markup(gui_text)
            else:
                plain = _strip_markup(record.getMessage())
            record.msg = plain
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


_REPLAY_BUFFER_SIZE = 5000
_MAX_LINE_WIDTH = 16384


class _GUIHandler(logging.Handler):
    """通知订阅者每条记录的格式化字符串与等级名；同时缓冲 5000 行供后来订阅者回放。
    所有共享态用继承的 self.lock 保护，应对 worker 线程并发 emit + 主线程 subscribe。"""

    def __init__(self) -> None:
        super().__init__()
        self._subscribers: list = []
        self._replay: deque = deque(maxlen=_REPLAY_BUFFER_SIZE)
        # 防递归 dispatch：cb 内若再调 logging.* 会触发同一 handler 的 emit，
        # 不加守卫会无限递归直到 RecursionError
        self._dispatching = threading.local()

    @staticmethod
    def _notify(cb, line: str, level: str, style: str, rows=None) -> None:
        try:
            cb(line, level, style, rows)
        except TypeError:
            try:
                cb(line, level, style)
            except TypeError:
                cb(line, level)

    def subscribe(self, cb, batch_cb=None) -> None:
        # 锁内：原子地决定回放与挂订阅，避免 emit 在两者之间塞入 record 而新 cb 漏收
        with self.lock:
            if cb in self._subscribers:
                return
            history = list(self._replay)
            self._subscribers.append(cb)
        # 锁外回放，cb 可能耗时或重入 logging
        if batch_cb is not None:
            try:
                batch_cb(history)
            except Exception:
                pass
            return
        for item in history:
            if len(item) >= 4:
                line, level, style, rows = item[:4]
            elif len(item) == 3:
                line, level, style = item
                rows = None
            else:
                line, level = item
                style = ""
                rows = None
            try:
                self._notify(cb, line, level, style, rows)
            except Exception:
                pass

    def unsubscribe(self, cb) -> None:
        with self.lock:
            try:
                self._subscribers.remove(cb)
            except ValueError:
                pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            if len(line) > _MAX_LINE_WIDTH:
                line = line[:_MAX_LINE_WIDTH] + " …(truncated)"
            level = record.levelname
            style = getattr(record, "ainiee_gui_style", "")
            if not isinstance(style, str):
                style = ""
            rows = getattr(record, "ainiee_gui_rows", None)
            if not isinstance(rows, list):
                rows = None
            with self.lock:
                self._replay.append((line, level, style, rows))
                # 同一线程已在 dispatch 里：只进 replay 不再分发，避免 cb 内
                # 调 logging.* 触发的无限递归
                if getattr(self._dispatching, "depth", 0) > 0:
                    return
                subscribers = list(self._subscribers)
            self._dispatching.depth = getattr(self._dispatching, "depth", 0) + 1
            try:
                for cb in subscribers:
                    try:
                        self._notify(cb, line, level, style, rows)
                    except Exception:
                        pass
            finally:
                self._dispatching.depth -= 1
        except Exception:
            self.handleError(record)


def _emergency_stderr(text: str) -> None:
    try:
        if sys.__stderr__ is not None:
            sys.__stderr__.write(redact(text) + "\n")
    except Exception:
        pass


class _BroadcastStream:
    """包裹 sys.stdout/stderr：原写入照常 + 按行 flush 到 logger（再到 root → file + gui）。

    _buffer 跨线程共享，用 self._lock 保护读写避免撕裂。
    若调用方是 LogMixin（_in_log_mixin.active），跳过 logger.log 以避免双写。
    """

    def __init__(self, original, logger_name: str, level: int) -> None:
        self._original = original
        self._logger = logging.getLogger(logger_name)
        self._level = level
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, text):
        if not text:
            return 0
        try:
            self._original.write(text)
        except Exception:
            pass
        if _in_log_mixin_active():
            return len(text)
        lines_to_log = []
        with self._lock:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line:
                    lines_to_log.append(line)
        for line in lines_to_log:
            # 终结期 handler 可能已 tear down，吞掉避免阻塞写路径
            try:
                self._logger.log(self._level, line)
            except Exception:
                _emergency_stderr(line)
        return len(text)

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass
        # 把 buffer 里没换行的尾巴也喂给 logger，避免 crash 前最后一行（如
        # tqdm 进度条、不带 \n 的诊断输出）只留在终端、不落 file。
        # 不需要 _in_log_mixin_active() 守卫——write() 在 LogMixin 上下文里 early-return
        # 不会进 buffer，所以这里能取到的 pending 必然来自非 LogMixin 路径，不会双写
        pending = ""
        with self._lock:
            if self._buffer:
                pending = self._buffer
                self._buffer = ""
        if pending:
            # atexit / Python 终结期 handler 可能已被关闭，吞掉避免污染退出流程
            try:
                self._logger.log(self._level, pending)
            except Exception:
                _emergency_stderr(pending)

    def isatty(self):
        try:
            return self._original.isatty()
        except Exception:
            return False

    def __getattr__(self, name):
        return getattr(self._original, name)


_gui_handler: Optional["_GUIHandler"] = None
_gui_handler_lock = threading.Lock()


def get_gui_handler() -> "_GUIHandler":
    """懒单例 GUI handler；首次调用时挂到 root logger，使用面向用户的简洁 formatter。"""
    global _gui_handler
    if _gui_handler is not None:
        return _gui_handler
    with _gui_handler_lock:
        if _gui_handler is not None:
            return _gui_handler
        handler = _GUIHandler()
        handler.setFormatter(_ConsoleFormatter())
        handler.addFilter(SensitiveFilter())
        logging.getLogger().addHandler(handler)
        _gui_handler = handler
        return _gui_handler


_DEVNULL = None


def _close_devnull() -> None:
    global _DEVNULL
    if _DEVNULL is not None:
        try:
            _DEVNULL.close()
        except Exception:
            pass
        _DEVNULL = None


def _ensure_std_streams() -> None:
    global _DEVNULL
    if sys.stdout is not None and sys.stderr is not None:
        return
    if _DEVNULL is None:
        _DEVNULL = open(os.devnull, "w")
        atexit.register(_close_devnull)
    if sys.stdout is None:
        sys.stdout = _DEVNULL
    if sys.stderr is None:
        sys.stderr = _DEVNULL


_original_excepthook = None
_original_thread_excepthook = None


def _crash_fallback(exc_type, exc_value, exc_tb) -> None:
    import traceback
    import tempfile
    try:
        text = redact("".join(traceback.format_exception(exc_type, exc_value, exc_tb))[:65536])
    except Exception:
        text = "AiNiee crash (traceback formatting failed)"
    _emergency_stderr(text)
    try:
        fallback = user_log_dir() / "crash_fallback.log"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        with open(fallback, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        try:
            with open(os.path.join(tempfile.gettempdir(), "ainiee_crash_fallback.log"), "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    try:
        logging.getLogger(CRASH_LOGGER_NAME).critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_tb)
        )
    except Exception:
        _crash_fallback(exc_type, exc_value, exc_tb)
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
        _crash_fallback(args.exc_type, args.exc_value, args.exc_traceback)
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
        fault_path = log_dir / FAULT_LOG_FILENAME
        try:
            if fault_path.stat().st_size > FAULT_MAX_BYTES:
                fault_path.unlink()
        except OSError:
            pass
        _fault_log_handle = open(fault_path, "a", buffering=1)
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
    # 早期就保证 stderr 非 None（PyInstaller --windowed 下 stderr 是 None），
    # 否则下面的失败分支 sys.stderr.write 会抛 AttributeError 把 install 整个崩
    _ensure_std_streams()
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
