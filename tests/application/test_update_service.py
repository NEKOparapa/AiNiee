import importlib
from unittest.mock import Mock

import pytest
import requests

from ModuleFolders.Application.UpdateService import UpdateCheckError, UpdateService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager


def release(version, asset_name="AiNiee.zip", **extra):
    return {
        "tag_name": version,
        "html_url": "https://example.invalid/releases/" + version,
        "assets": [{"name": asset_name, "browser_download_url": "https://example.invalid/archive"}],
        **extra,
    }


def response(data, status_code=200):
    return Mock(status_code=status_code, json=Mock(return_value=data))


@pytest.fixture(autouse=True)
def windows_asset_selection(monkeypatch):
    module = importlib.import_module("ModuleFolders.Application.UpdateService")
    monkeypatch.setattr(module, "is_macos", lambda: False)


def test_check_selects_compatible_new_version_with_fixed_http_response():
    get = Mock(return_value=response(release("v7.10.0")))
    result = UpdateService("AiNiee 7.2.6", http_get=get).check()
    assert result == {
        "current_version": "7.2.6",
        "latest_version": "7.10.0",
        "update_available": True,
        "release_url": "https://example.invalid/releases/v7.10.0",
    }
    assert get.call_count == 1
    assert get.call_args.kwargs["timeout"] == 10


def test_version_comparison_pads_missing_segments():
    get = Mock(return_value=response(release("v7.2.0")))
    result = UpdateService("AiNiee 7.2", http_get=get).check()
    assert result["update_available"] is False
    assert get.call_count == 1


def test_check_falls_back_to_platform_compatible_stable_release():
    get = Mock(side_effect=[
        response(release("v9.0", "AiNiee-arm64.dmg")),
        response([
            release("v9.0", "AiNiee-arm64.dmg"),
            release("v10.0", prerelease=True),
            release("v11.0", draft=True),
            release("v7.4"),
            release("v7.3"),
        ]),
    ])
    result = UpdateService("7.2.6", http_get=get).check()
    assert result["latest_version"] == "7.4"
    assert result["update_available"] is True
    assert get.call_args.kwargs["params"] == {"per_page": 100, "page": 1}
    assert not get.call_args.args[0].endswith("/latest")


@pytest.mark.parametrize("status", [403, 404, 500])
def test_http_failure_is_an_application_error(status):
    with pytest.raises(UpdateCheckError, match=f"HTTP {status}"):
        UpdateService("7.2.6", http_get=Mock(return_value=response({}, status))).check()


def test_network_and_invalid_json_failures_are_application_errors():
    with pytest.raises(UpdateCheckError, match="Unable to reach"):
        UpdateService("7.2.6", http_get=Mock(side_effect=requests.Timeout())).check()
    invalid = response(None)
    invalid.json.side_effect = ValueError("invalid json")
    with pytest.raises(UpdateCheckError, match="invalid JSON"):
        UpdateService("7.2.6", http_get=Mock(return_value=invalid)).check()


def test_macos_uses_architecture_compatible_asset(monkeypatch):
    module = importlib.import_module("ModuleFolders.Application.UpdateService")
    monkeypatch.setattr(module, "is_macos", lambda: True)
    monkeypatch.setenv("AINIEE_MACOS_ARCH", "aarch64")
    get = Mock(return_value=response(release("v7.3", "AiNiee-arm64.dmg")))
    assert UpdateService("7.2.6", http_get=get).check()["update_available"] is True


def test_macos_missing_release_preserves_old_no_update_behavior(monkeypatch):
    module = importlib.import_module("ModuleFolders.Application.UpdateService")
    monkeypatch.setattr(module, "is_macos", lambda: True)
    get = Mock(return_value=response({}, 404))
    assert UpdateService("7.2.6", http_get=get).check()["update_available"] is False


def test_successful_check_broadcasts_the_same_result():
    manager = EventManager.get_singleton()
    events = []

    def receive(event, data):
        events.append((event, data))

    manager.subscribe(Base.EVENT.APP_UPDATE_CHECK_DONE, receive)
    try:
        get = Mock(return_value=response(release("v7.3")))
        result = UpdateService("7.2.6", http_get=get).check()
        assert events == [(Base.EVENT.APP_UPDATE_CHECK_DONE, result)]
    finally:
        manager.unsubscribe(Base.EVENT.APP_UPDATE_CHECK_DONE, receive)


def test_failed_check_broadcasts_safe_error_and_reraises():
    manager = EventManager.get_singleton()
    events = []

    def receive(event, data):
        events.append(data)

    manager.subscribe(Base.EVENT.APP_UPDATE_CHECK_DONE, receive)
    try:
        get = Mock(side_effect=requests.Timeout("https://private.invalid?api_key=secret"))
        with pytest.raises(UpdateCheckError, match="Unable to reach"):
            UpdateService("7.2.6", http_get=get).check()
        assert events == [{"status": "error", "message": "Unable to check for updates"}]
    finally:
        manager.unsubscribe(Base.EVENT.APP_UPDATE_CHECK_DONE, receive)
