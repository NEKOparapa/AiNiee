import importlib
import json

import pytest

from ModuleFolders.Application.SystemService import ShutdownUnavailableError, SystemService


def test_version_reads_existing_resource_format(tmp_path, monkeypatch):
    version_file = tmp_path / "version.json"
    version_file.write_text(json.dumps({"version": "AiNiee 7.2.6"}), encoding="utf-8")
    module = importlib.import_module("ModuleFolders.Application.SystemService")
    monkeypatch.setattr(module, "resource_path", lambda *args: version_file)
    assert SystemService().get_version() == {"version": "AiNiee 7.2.6"}


@pytest.mark.parametrize("contents", [None, "invalid", "[]", '{"version": 42}'])
def test_version_falls_back_for_missing_or_invalid_resource(tmp_path, monkeypatch, contents):
    version_file = tmp_path / "version.json"
    if contents is not None:
        version_file.write_text(contents, encoding="utf-8")
    module = importlib.import_module("ModuleFolders.Application.SystemService")
    monkeypatch.setattr(module, "resource_path", lambda *args: version_file)
    assert SystemService().get_version() == {"version": "Unknown Version"}


def test_shutdown_only_calls_the_injected_process_callback():
    calls = []
    service = SystemService(shutdown_callback=lambda: calls.append("shutdown"))
    assert service.get_health() == {"status": "ok"}
    assert service.request_shutdown() == {"status": "shutting_down"}
    assert calls == ["shutdown"]
    with pytest.raises(ShutdownUnavailableError):
        SystemService().request_shutdown()
