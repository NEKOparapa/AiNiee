import os
import subprocess
import sys
from pathlib import Path

from ModuleFolders.Application.Bootstrap import bootstrap
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager


def test_bootstrap_shares_dependencies_and_cleans_up_subscriptions():
    manager = EventManager.get_singleton()
    before = manager.event_callbacks
    with bootstrap() as runtime:
        assert runtime.task_executor.cache_manager is runtime.cache_manager
        assert runtime.task_executor.file_reader is runtime.file_reader
        assert runtime.task_executor.file_writer is runtime.file_writer
        assert runtime.cache_manager.project is None
        assert Base.work_status == Base.STATUS.IDLE
        assert len(manager.event_callbacks[Base.EVENT.TASK_START]) == 2
    runtime.close()
    assert runtime.cache_manager.save_to_file_stop_flag
    assert manager.event_callbacks == before


def test_bootstrap_imports_without_gui_dependencies():
    # 子进程显式阻断 GUI import；在开发机装有旧界面依赖时也能回归验证。
    script = """
import importlib.abc
import socket
import sys

class NoGuiImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.')[0].lower()
        if root.startswith(('pyqt', 'pyside', 'qfluent', 'userinterface')) or root == 'fastapi':
            raise AssertionError('Unexpected UI/transport dependency: ' + fullname)

def no_network(*args, **kwargs):
    raise AssertionError('Unexpected network request during bootstrap')

sys.meta_path.insert(0, NoGuiImports())
socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network
from ModuleFolders.Application.Bootstrap import bootstrap
with bootstrap() as runtime:
    assert runtime.cache_manager.project is None
print('BOOTSTRAP_OK')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "BOOTSTRAP_OK" in result.stdout
