import importlib
import platform

import pytest


def _reload_si():
    import ModuleFolders.Infrastructure.Platform.SingleInstance as si
    importlib.reload(si)
    return si


class TestAcquireAppMutex:
    def test_non_windows_is_noop(self):
        if platform.system() == "Windows":
            pytest.skip("Windows-only check")
        si = _reload_si()
        si.acquire_app_mutex()
        assert si._handle is None  # no-op，不获取句柄

    def test_idempotent(self):
        """同一进程多次调用不应炸或重复获取。"""
        si = _reload_si()
        si.acquire_app_mutex()
        si.acquire_app_mutex()
        si.acquire_app_mutex()
        # 不抛即为通过；具体 _handle 状态依平台

    def test_mutex_name_matches_installer_constant(self):
        """与 Inno Setup .iss 里 AppMutex= 必须同名，否则失效。"""
        si = _reload_si()
        assert si.APP_MUTEX_NAME == "AiNieeAppMutex"
        iss = open("Tools/Installer/ainiee.iss", encoding="utf-8").read()
        assert f"AppMutex={si.APP_MUTEX_NAME}" in iss
