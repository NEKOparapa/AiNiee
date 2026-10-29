"""测试默认隔离用户数据，并禁止真实网络连接。"""

import ipaddress
import socket
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def check_address(address):
        host = address[0] if isinstance(address, tuple) else ""
        try:
            allowed = host == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            allowed = False
        if not allowed:
            raise AssertionError("Tests must use fixed mocks instead of external network requests")

    # Windows asyncio creates an internal loopback socketpair. HTTP integration
    # tests also need loopback; external connections remain forbidden.
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def guarded(self, address, _original=original):
            check_address(address)
            return _original(self, address)

        monkeypatch.setattr(socket.socket, name, guarded)

    original_sendto = socket.socket.sendto
    original_create = socket.create_connection

    def guarded_sendto(self, data, *args):
        check_address(args[-1])
        return original_sendto(self, data, *args)

    def guarded_create(address, *args, **kwargs):
        check_address(address)
        return original_create(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket, "create_connection", guarded_create)


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
