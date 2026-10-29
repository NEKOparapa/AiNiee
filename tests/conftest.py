"""测试默认隔离用户数据，并禁止真实网络连接。"""

import socket
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must use fixed mocks instead of network requests")

    for name in ("connect", "connect_ex", "sendto"):
        monkeypatch.setattr(socket.socket, name, blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture(autouse=True)
def isolated_app_paths(tmp_path, monkeypatch):
    resource_dir = Path(__file__).resolve().parents[1] / "Resource"
    monkeypatch.setenv("AINIEE_PORTABLE", "1")
    monkeypatch.setenv("AINIEE_RESOURCE_DIR", str(resource_dir))
    for name, directory in (
        ("AINIEE_USER_DATA_DIR", "data"),
        ("AINIEE_CACHE_DIR", "cache"),
        ("AINIEE_PROJECT_CACHE_DIR", "projects"),
        ("AINIEE_TIKTOKEN_CACHE_DIR", "tiktoken"),
        ("AINIEE_LOG_DIR", "logs"),
        ("AINIEE_DOWNLOADS_DIR", "downloads"),
        ("AINIEE_DOCUMENTS_DIR", "documents"),
    ):
        monkeypatch.setenv(name, str(tmp_path / directory))

    from ModuleFolders.Base.Base import Base
    from ModuleFolders.Config import FilePathConfig
    from ModuleFolders.Infrastructure.Tokener import BabeldocPatch, TiktokenLoader

    monkeypatch.setattr(FilePathConfig, "executable_root", lambda: tmp_path)
    monkeypatch.setattr(FilePathConfig, "_PORTABLE_WRITABLE_CACHE", None)
    monkeypatch.setattr(Base, "work_status", Base.STATUS.IDLE)
    monkeypatch.setattr(TiktokenLoader, "_TIKTOKEN_INITIALIZED", False)
    monkeypatch.setattr(TiktokenLoader, "_TIKTOKEN_CACHE_DIR", None)
    # 使已有初始化器对环境变量的写入也能在测试结束时撤销。
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path / "tiktoken"))
    yield tmp_path
    BabeldocPatch.remove_patch()
