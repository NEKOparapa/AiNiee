"""Serialize state-changing application operations around the legacy task state."""

from contextlib import contextmanager
from threading import RLock

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Base.Base import Base


OPERATION_LOCK = RLock()
_background_owner = None


def claim_background_operation(owner: object) -> None:
    """Reserve the application until its worker has actually finished cleanup."""
    global _background_owner
    with OPERATION_LOCK:
        if _background_owner is not None:
            raise ApplicationError("operation_busy", 409)
        _background_owner = owner


def release_background_operation(owner: object) -> None:
    global _background_owner
    with OPERATION_LOCK:
        if _background_owner is owner:
            _background_owner = None


@contextmanager
def exclusive_operation(status: int | None = None):
    if not OPERATION_LOCK.acquire(blocking=False):
        raise ApplicationError("operation_busy", 409)
    previous = Base.work_status
    try:
        if _background_owner is not None or previous not in (Base.STATUS.IDLE, Base.STATUS.TASKSTOPPED):
            raise ApplicationError("operation_busy", 409)
        if status is not None:
            Base.work_status = status
        yield
    finally:
        if status is not None and Base.work_status == status:
            Base.work_status = previous
        OPERATION_LOCK.release()
