import importlib
import logging
import sys
import threading

import pytest


@pytest.fixture
def tmp_log_dir(tmp_path, monkeypatch):
    """隔离日志目录，并 reload FileBackend 让 env override 生效，结束后清理 root handler。

    teardown 不仅移除 handler 与重置 _INSTALLED，还 reload fpc/fb 让模块全局
    回到干净态，避免测试顺序耦合（先跑过 tmp_log_dir 的测试 → 影响后续不带
    fixture 的测试）。
    """
    monkeypatch.setenv("AINIEE_LOG_DIR", str(tmp_path))

    import ModuleFolders.Config.FilePathConfig as fpc
    import ModuleFolders.Log.FileBackend as fb
    importlib.reload(fpc)
    importlib.reload(fb)

    yield tmp_path

    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "name", "") == fb.HANDLER_NAME:
            root.removeHandler(handler)
            handler.close()
    fb._INSTALLED = False
    # 还原模块到不带 env override 的形态
    importlib.reload(fpc)
    importlib.reload(fb)


@pytest.fixture
def clean_crash_hooks():
    """保存 / 还原 sys.excepthook + threading.excepthook，并重载 CrashHook 模块状态。"""
    import ModuleFolders.Log.CrashHook as ch
    importlib.reload(ch)

    original_sys_hook = sys.excepthook
    original_thread_hook = threading.excepthook
    try:
        yield ch
    finally:
        sys.excepthook = original_sys_hook
        threading.excepthook = original_thread_hook
        ch._INSTALLED = False
        ch._original_excepthook = None
        ch._original_thread_excepthook = None
