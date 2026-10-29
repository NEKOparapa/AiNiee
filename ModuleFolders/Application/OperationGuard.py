"""Serialize state-changing application operations around the legacy task state."""

from contextlib import contextmanager
from threading import RLock

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Base.Base import Base


OPERATION_LOCK = RLock()


@contextmanager
def exclusive_operation(status: int | None = None):
    if not OPERATION_LOCK.acquire(blocking=False):
        raise ApplicationError("operation_busy", 409)
    previous = Base.work_status
    try:
        if previous not in (Base.STATUS.IDLE, Base.STATUS.TASKSTOPPED):
            raise ApplicationError("operation_busy", 409)
        if status is not None:
            Base.work_status = status
        yield
    finally:
        if status is not None and Base.work_status == status:
            Base.work_status = previous
        OPERATION_LOCK.release()
