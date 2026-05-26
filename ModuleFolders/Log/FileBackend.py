"""日志落盘：根 logger 上挂 RotatingFileHandler，并做敏感信息脱敏与 rich 标记剥离。"""

import logging
import logging.handlers
import re
import time
from pathlib import Path

from rich.text import Text

from ModuleFolders.Config.FilePathConfig import user_log_dir


LOG_FILENAME = "ainiee.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5
RETENTION_DAYS = 30
HANDLER_NAME = "ainiee_file"
REDACTED = "***REDACTED***"

_LOG_FILE_RE = re.compile(r"^ainiee\.log(\.\d+)?$")

_API_KEY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"ya29\.[0-9A-Za-z._\-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE),
)

_NOISY_THIRD_PARTY = ("urllib3", "httpcore", "httpx", "PIL", "matplotlib", "asyncio")

_INSTALLED = False


class SensitiveFilter(logging.Filter):
    @staticmethod
    def _redact(text: str) -> str:
        for pat in _API_KEY_PATTERNS:
            text = pat.sub(REDACTED, text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = self._redact(msg)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        if record.exc_info:
            # 预格式化并脱敏 traceback，写入 record.exc_text。
            # Formatter 见 exc_text 已存在就不会再调 formatException，避免重渲泄漏。
            exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_text = self._redact(exc_text)
        return True


class _PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg = record.msg
        original_args = record.args
        try:
            text = record.getMessage()
            record.msg = Text.from_markup(text).plain
            record.args = ()
            return super().format(record)
        except Exception:
            record.msg = original_msg
            record.args = original_args
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


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


def init_file_logging() -> Path:
    """挂载文件 handler 到根 logger，可重入。返回日志文件路径。"""
    global _INSTALLED
    log_dir = user_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / LOG_FILENAME

    root = logging.getLogger()
    for existing in root.handlers:
        if getattr(existing, "name", "") == HANDLER_NAME:
            _INSTALLED = True
            return log_path

    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(
        _PlainFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    handler.addFilter(SensitiveFilter())
    handler.set_name(HANDLER_NAME)

    if root.level == logging.WARNING or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)
    root.addHandler(handler)

    for noisy in _NOISY_THIRD_PARTY:
        lg = logging.getLogger(noisy)
        if lg.level == logging.NOTSET or lg.level < logging.WARNING:
            lg.setLevel(logging.WARNING)

    _cleanup_old_logs(log_dir, RETENTION_DAYS)
    _INSTALLED = True
    return log_path
