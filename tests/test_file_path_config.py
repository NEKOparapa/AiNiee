import importlib
import platform
from pathlib import Path

import pytest


def _reload_fpc():
    import ModuleFolders.Config.FilePathConfig as fpc
    importlib.reload(fpc)
    return fpc


class TestUserLogDir:
    def test_env_override_takes_precedence_over_platform_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AINIEE_LOG_DIR", str(tmp_path))
        fpc = _reload_fpc()
        assert fpc.user_log_dir() == tmp_path.resolve()

    def test_env_override_expands_user_home(self, monkeypatch):
        monkeypatch.setenv("AINIEE_LOG_DIR", "~/ainiee-logs-test")
        fpc = _reload_fpc()
        assert fpc.user_log_dir() == (Path.home() / "ainiee-logs-test").resolve()

    def test_macos_default_is_library_logs(self, monkeypatch):
        if platform.system() != "Darwin":
            pytest.skip("macOS-only behavior")
        monkeypatch.delenv("AINIEE_LOG_DIR", raising=False)
        fpc = _reload_fpc()
        assert fpc.user_log_dir() == Path.home() / "Library" / "Logs" / "AiNiee"

    def test_non_macos_default_ends_in_logs(self, monkeypatch):
        if platform.system() == "Darwin":
            pytest.skip("non-macOS path")
        monkeypatch.delenv("AINIEE_LOG_DIR", raising=False)
        fpc = _reload_fpc()
        assert fpc.user_log_dir().name == "Logs"

    def test_returns_path_object(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AINIEE_LOG_DIR", str(tmp_path))
        fpc = _reload_fpc()
        assert isinstance(fpc.user_log_dir(), Path)
