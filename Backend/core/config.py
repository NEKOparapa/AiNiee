"""Backend-local configuration access. Desktop clients use the configuration API."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps

from Backend.infrastructure.config.store import ConfigStore


_TASK_CONFIG = ContextVar("task_config_snapshot", default=None)


def get_config_snapshot():
    """Return a private copy of this operation's settings, or None outside a task."""
    snapshot = _TASK_CONFIG.get()
    return deepcopy(snapshot) if snapshot is not None else None


@contextmanager
def config_snapshot(snapshot: dict):
    """Freeze task reads while leaving ConfigStore and explicit writes live.

    Runtime captures persisted settings at submission and enters this context in
    its worker. ContextVar isolates concurrent workers and restores nested calls.
    """
    if not isinstance(snapshot, dict):
        raise TypeError("configuration snapshot must be a dictionary")
    token = _TASK_CONFIG.set(deepcopy(snapshot))
    try:
        yield
    finally:
        _TASK_CONFIG.reset(token)


def bind_config_snapshot(callback):
    """Capture settings for a child thread which needs to load configuration.

    ThreadPoolExecutor does not inherit ContextVars. Existing request workers
    receive resolved TaskConfig objects; use this wrapper for new workers that
    call load_config/read_snapshot themselves.
    """
    snapshot = get_config_snapshot()
    if snapshot is None:
        return callback

    @wraps(callback)
    def run(*args, **kwargs):
        with config_snapshot(snapshot):
            return callback(*args, **kwargs)

    return run


class ConfigMixin(ConfigStore):
    def load_config(self):
        snapshot = get_config_snapshot()
        return snapshot if snapshot is not None else super().load_config()

    def load_config_from_default(self):
        return self.fill_config(self.load_config(), getattr(self, "default", {}))
