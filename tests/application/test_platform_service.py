import json
import threading
from types import SimpleNamespace

import httpx
import pytest

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.PlatformService import PlatformService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.LogSystem import redact, sensitive_values


def create_platform(service, **changes):
    return service.create_platform({
        "preset_id": "custom", "name": "Fixed mock", "model": "fixed-model",
        "api_url": "https://llm.invalid", "api_key": "fixed-short-key", **changes,
    })


def test_create_update_delete_preserve_config_and_never_overwrite_presets():
    service = PlatformService()
    ConfigMixin().save_config({"unrelated": {"keep": True}, "platforms": {}})
    before_presets = service._presets()
    first = create_platform(service)
    second = create_platform(service, name="Second")
    first_id, second_id = first["id"], second["id"]
    assert first_id != second_id
    assert first["tag"] == first_id
    assert "fixed-model" in first["model_datas"]
    assert service._presets() == before_presets

    ConfigMixin().update_config(lambda config: config["platforms"][first_id].update({"extension": {"keep": 42}}))
    result = service.update_platform(first_id, {"name": " Renamed ", "model": "new-model", "extra_headers": {"X-Provider": "fixed"}})
    assert result["name"] == "Renamed"
    assert result["api_key"] == "fixed-short-key"
    assert result["extension"] == {"keep": 42}
    assert result["extra_headers"] == {"x-provider": "fixed"}
    assert "new-model" in result["model_datas"]
    bindings = {"active": first_id, "extract": None, "translate": first_id, "polish": second_id, "proofread": None}
    assert service.update_bindings(bindings) == bindings
    service.delete_platform(first_id)
    saved = ConfigMixin().load_config()
    assert first_id not in saved["platforms"]
    assert second_id in saved["platforms"]
    assert saved["unrelated"] == {"keep": True}
    # Existing normalization falls back to the first explicitly bound platform.
    assert saved["api_settings"]["active"] == second_id
    assert saved["api_settings"]["translate"] is None


def test_legacy_binding_migration_and_missing_fields_are_view_only():
    service = PlatformService()
    original = {
        "platforms": {"custom_old": {"name": "Legacy", "model": "old", "extension": 2}},
        "api_settings": {role: "custom_old" for role in ("active", "extract", "translate", "polish", "proofread")},
    }
    ConfigMixin().save_config(original)
    before = ConfigMixin().load_config()
    response = service.list_platforms()
    assert response["bindings"] == {"active": "custom_old", "extract": None, "translate": None, "polish": None, "proofread": None}
    assert response["platforms"][0]["extension"] == 2
    assert response["platforms"][0]["api_format"] == "OpenAI"
    assert ConfigMixin().load_config() == before
    service.update_platform("custom_old", {"name": "Kept"})
    saved = ConfigMixin().load_config()
    assert saved["api_settings"]["_active_follow_migration_done"] is True
    assert "api_format" not in saved["platforms"]["custom_old"]


def test_metadata_reuses_model_and_provider_rules():
    service = PlatformService()
    google = create_platform(service, api_format="Google", model="gemini-3.7-flash")
    assert "thinking_level" in google["metadata"]["fields"]
    assert "thinking_budget" not in google["metadata"]["fields"]
    assert "think_depth" not in google["metadata"]["fields"]
    assert google["metadata"]["thinking_level_options"] == ["low", "medium", "high"]
    legacy = service.update_platform(google["id"], {"model": "gemini-2.5-flash"})
    assert "thinking_budget" in legacy["metadata"]["fields"]
    assert "thinking_level" not in legacy["metadata"]["fields"]
    xai = service.create_platform({"preset_id": "xai", "name": "xAI", "model": "grok"})
    assert xai["metadata"]["think_depth_options"] == ["low", "medium", "high", "xhigh"]


@pytest.mark.parametrize("changes", [{"name": " "}, {"model": " "}, {"tag": "replace-id"}, {"extra_headers": {"X-Test": "bad\nheader"}}])
def test_invalid_updates_do_not_change_config(changes):
    service = PlatformService()
    platform = create_platform(service)
    before = ConfigMixin().load_config()
    with pytest.raises(ApplicationError):
        service.update_platform(platform["id"], changes)
    assert ConfigMixin().load_config() == before


def test_invalid_bindings_and_missing_ids_are_rejected():
    service = PlatformService()
    with pytest.raises(ApplicationError):
        service.update_bindings({"translate": "missing"})
    with pytest.raises(ApplicationError):
        service.delete_platform("missing")
    with pytest.raises(ApplicationError):
        service.create_platform({"preset_id": "custom", "name": "No URL", "model": "fixed"})


def test_mutations_are_rejected_during_task(monkeypatch):
    service = PlatformService()
    platform = create_platform(service)
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    with pytest.raises(ApplicationError):
        service.update_platform(platform["id"], {"name": "Busy"})
    assert service.list_platforms()["platforms"][0]["name"] == "Fixed mock"


@pytest.mark.parametrize(("api_format", "expected_path", "expected_header"), [
    ("OpenAI", "/v1/models", "authorization"),
    ("Anthropic", "/v1/models", "x-api-key"),
])
def test_model_browser_uses_fixed_http_transport(monkeypatch, api_format, expected_path, expected_header):
    service = PlatformService()
    platform = create_platform(service, api_format=api_format, api_url="https://llm.invalid/v1", api_key=" first-key , second-key ")
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.path == expected_path
        assert "first-key" in request.headers[expected_header]
        assert "second-key" not in request.headers[expected_header]
        return httpx.Response(200, json={"data": [{"id": "fixed-z"}, {"id": "fixed-a"}, {"id": "fixed-z"}, {"id": "image-model"}]})

    client_type = httpx.Client
    monkeypatch.setattr("ModuleFolders.Application.PlatformService.httpx.Client", lambda **kwargs: client_type(transport=httpx.MockTransport(handler)))
    assert service.get_models(platform["id"]) == {"platform_id": platform["id"], "models": ["fixed-a", "fixed-z"]}
    assert len(requests) == 1


def test_model_errors_do_not_echo_provider_secrets(monkeypatch):
    service = PlatformService()
    platform = create_platform(service)

    def fail(*args):
        raise RuntimeError("provider reflected fixed-short-key")

    monkeypatch.setattr(service, "_fetch_models", fail)
    with pytest.raises(ApplicationError) as error:
        service.get_models(platform["id"])
    assert "fixed-short-key" not in str(error.value)
    assert "model_fetch_failed" in str(error.value)


def test_google_models_filter_without_any_network(monkeypatch):
    from ModuleFolders.Infrastructure.LLMRequester.LLMClientFactory import LLMClientFactory

    models = [SimpleNamespace(name=name) for name in ("models/gemini-fixed", "models/gemma-fixed", "models/gemini-image", "models/gemini-live", "models/embedding")]
    monkeypatch.setattr(LLMClientFactory, "get_google_client", lambda self, config: SimpleNamespace(models=SimpleNamespace(list=lambda: models)))
    service = PlatformService()
    platform = create_platform(service, api_format="Google")
    assert service.get_models(platform["id"])["models"] == ["gemini-fixed", "gemma-fixed"]


def test_sensitive_values_are_nested_and_thread_isolated():
    results = []
    with sensitive_values(["short-provider-key"]):
        assert "short-provider-key" not in redact("failure: short-provider-key")
        with sensitive_values(["nested-secret"]):
            assert "nested-secret" not in redact("nested-secret short-provider-key")
        assert redact("nested-secret") == "nested-secret"
        worker = threading.Thread(target=lambda: results.append(redact("short-provider-key")))
        worker.start()
        worker.join()
    assert results == ["short-provider-key"]
    assert redact("short-provider-key") == "short-provider-key"


def test_platform_test_runs_each_key_and_restores_status_before_done(monkeypatch):
    from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester

    service = PlatformService()
    platform = create_platform(service, api_url="https://llm.invalid/chat/completions/", api_key=" first-key,\n second-key ,third-key ")
    before = ConfigMixin().load_config()
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKSTOPPED)
    calls, events = [], []

    def fixed_request(self, messages, system_prompt, config):
        assert Base.work_status == Base.STATUS.API_TEST
        assert messages == [{"role": "user", "content": "小可爱，你在干嘛"}]
        assert config["api_url"] == "https://llm.invalid/v1"
        assert config["model_name"] == "fixed-model"
        calls.append(config["api_key"])
        if config["api_key"] == "second-key":
            raise RuntimeError("provider reflected second-key")
        return config["api_key"] == "third-key", "", "fixed response", 8, 4

    def on_done(event, data):
        events.append((Base.work_status, data))

    monkeypatch.setattr(LLMRequester, "sent_request", fixed_request)
    manager = EventManager.get_singleton()
    manager.subscribe(Base.EVENT.API_TEST_DONE, on_done)
    try:
        result = service.test_platform(platform["id"])
    finally:
        manager.unsubscribe(Base.EVENT.API_TEST_DONE, on_done)
    assert calls == ["first-key", "second-key", "third-key"]
    assert result == {
        "platform_id": platform["id"], "success_count": 1, "failure_count": 2,
        "results": [
            {"key_index": 1, "success": True, "error_code": None},
            {"key_index": 2, "success": False, "error_code": "platform_test_failed"},
            {"key_index": 3, "success": False, "error_code": "platform_test_failed"},
        ],
    }
    assert Base.work_status == Base.STATUS.TASKSTOPPED
    assert events == [(Base.STATUS.TASKSTOPPED, result)]
    assert all(key not in json.dumps(result) for key in calls)
    assert ConfigMixin().load_config() == before


def test_api_testing_excludes_other_operations_and_recovers(monkeypatch):
    from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester

    service = PlatformService()
    platform = create_platform(service)
    entered, release = threading.Event(), threading.Event()
    results = []

    def fixed_request(*args):
        entered.set()
        assert release.wait(5)
        raise RuntimeError("Fixed request failed")

    monkeypatch.setattr(LLMRequester, "sent_request", fixed_request)
    worker = threading.Thread(target=lambda: results.append(service.test_platform(platform["id"])))
    worker.start()
    try:
        assert entered.wait(5)
        assert Base.work_status == Base.STATUS.API_TEST
        with pytest.raises(ApplicationError, match="operation_busy"):
            service.test_platform(platform["id"])
        with pytest.raises(ApplicationError, match="operation_busy"):
            service.delete_platform(platform["id"])
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert results[0]["failure_count"] == 1
    assert Base.work_status == Base.STATUS.IDLE


def test_missing_test_platform_restores_status():
    with pytest.raises(ApplicationError, match="platform_not_found"):
        PlatformService().test_platform("missing")
    assert Base.work_status == Base.STATUS.IDLE


@pytest.mark.parametrize(("platform_id", "config", "expected"), [
    ("custom_123", {"api_url": "https://llm.invalid/v1/chat/completions", "api_format": "OpenAI", "auto_complete": True}, "https://llm.invalid/v1"),
    ("anthropic_123", {"api_url": "https://llm.invalid/v1", "api_format": "Anthropic", "auto_complete": True}, "https://llm.invalid"),
    ("sakura_123", {"api_url": "http://127.0.0.1:8080", "api_format": "OpenAI", "auto_complete": False}, "http://127.0.0.1:8080/v1"),
    ("custom_123", {"api_url": "https://llm.invalid/api", "api_format": "OpenAI", "auto_complete": False}, "https://llm.invalid/api"),
])
def test_api_test_url_completion(platform_id, config, expected):
    assert PlatformService._test_url(platform_id, config) == expected
