"""Start a separately installed backend without importing its Python modules."""
from contextlib import contextmanager
import getpass
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

from Frontend.core.paths import backend_log_dir, repo_root


# This bootstrap runs in the child interpreter, not the desktop process. Its
# stdlib-only fallback records missing packages and other early startup errors
# before the backend's rotating logger is available. Normal output is recorded
# by the backend itself, so there is only one writer for its main log.
_BACKEND_BOOTSTRAP = """\
import logging, os, runpy, sys
try:
    runpy.run_module("Backend", run_name="__main__", alter_sys=True)
except BaseException as error:
    if isinstance(error, SystemExit) and error.code in (None, 0):
        raise
    root = logging.getLogger()
    if not any(handler.name == "ainiee_file" for handler in root.handlers):
        logging.basicConfig(
            filename=os.path.join(os.environ["AINIEE_BACKEND_LOG_DIR"], "ainiee.log"),
            encoding="utf-8", level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", force=True,
        )
    logger = logging.getLogger("AiNiee.bootstrap")
    if isinstance(error, SystemExit):
        logger.error("Backend exited with status %s", error.code)
        raise
    logger.exception("Backend startup or runtime failed")
    sys.exit(1)
"""


def backend_port_available(host, port):
    # Windows can report ConnectTimeout even for an unused loopback port.
    # Check the bind address before starting, including an existing listener
    # whose accept queue is full or which has not started serving HTTP yet.
    for family, kind, protocol, _, address in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        with socket.socket(family, kind, protocol) as probe:
            if os.name == "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind(address)
            except OSError:
                return False
    return True


@contextmanager
def backend_startup_lock(port, deadline):
    # localhost and 127.0.0.1 share this lock. Keep the file after unlocking:
    # deleting it could let another process lock a different inode on Unix.
    user = hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]
    path = Path(tempfile.gettempdir()) / f"ainiee-backend-{user}-{port}.lock"
    with open(path, "a+b") as lock:
        if path.stat().st_size == 0:
            lock.write(b"0")
            lock.flush()
        if os.name == "nt":
            import msvcrt
        else:
            import fcntl
        while True:
            try:
                lock.seek(0)
                if os.name == "nt":
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("等待其他启动进程启动后端超时")
                time.sleep(0.1)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def launch_backend(host, port):
    python = os.environ.get("AINIEE_BACKEND_PYTHON")
    if not python:
        if getattr(sys, "frozen", False):
            raise RuntimeError("请设置 AINIEE_BACKEND_PYTHON 指向后端 Python 解释器，或先手动启动后端")
        python = sys.executable
    directory = Path(os.environ.get("AINIEE_BACKEND_DIR", str(repo_root()))).expanduser().resolve()
    log_path = backend_log_dir() / "ainiee.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        process = subprocess.Popen(
            [python, "-c", _BACKEND_BOOTSTRAP, "--host", host, "--port", str(port)],
            cwd=directory,
            env={**os.environ, "AINIEE_BACKEND_LOG_DIR": str(log_path.parent),
                "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
    except OSError as error:
        # No child exists yet, so recording launch failure cannot race its logger.
        from Frontend.core.log_system import redact
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [ERROR] AiNiee.bootstrap: {redact(str(error))}\n")
        raise RuntimeError(f"无法启动后端，请检查解释器和目录。后端日志：{log_path}") from error
    return process, log_path
