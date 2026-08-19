import importlib.util
from pathlib import Path

from ainiee_mcp import paths


def test_direct_override(monkeypatch, tmp_path):
    cfg = tmp_path / "custom.json"
    monkeypatch.setenv("AINIEE_CONFIG", str(cfg))
    assert paths.config_path() == cfg.resolve()


def test_user_data_override(monkeypatch, tmp_path):
    monkeypatch.delenv("AINIEE_CONFIG", raising=False)
    monkeypatch.setenv("AINIEE_USER_DATA_DIR", str(tmp_path))
    assert paths.config_path() == tmp_path.resolve() / "config.json"


def _load_real_filepathconfig():
    real = paths.repo_root() / "ModuleFolders" / "Config" / "FilePathConfig.py"
    if not real.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_real_fpc", real)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parity_with_real_filepathconfig(monkeypatch, tmp_path):
    """Our config_path must agree with AiNiee's own under the user-data override."""
    real = _load_real_filepathconfig()
    if real is None:
        return  # AiNiee repo not alongside; skip parity
    monkeypatch.delenv("AINIEE_CONFIG", raising=False)
    monkeypatch.setenv("AINIEE_USER_DATA_DIR", str(tmp_path))
    assert paths.config_path() == real.config_path()
