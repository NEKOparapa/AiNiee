"""未捕获异常落盘 + PyInstaller --windowed 下 stdout/stderr 为 None 的兜底。

install_crash_hooks() 应在 init_file_logging() 之后调用。
"""

import logging
import os
import sys
import threading


CRASH_LOGGER_NAME = "AiNiee.crash"

_INSTALLED = False
_original_excepthook = None
_original_thread_excepthook = None
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


def install_crash_hooks() -> None:
    global _INSTALLED, _original_excepthook, _original_thread_excepthook
    if _INSTALLED:
        return
    _ensure_std_streams()
    _original_excepthook = sys.excepthook
    sys.excepthook = _excepthook
    _original_thread_excepthook = threading.excepthook
    threading.excepthook = _thread_excepthook
    _INSTALLED = True
