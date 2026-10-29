from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from Server.app import create_app
from Server.schemas.platforms import PlatformListResponse


AUTH = {"Authorization": "Bearer platform-test-token"}


@pytest.fixture
def client():
    cache = CacheManager()
    runtime = SimpleNamespace(cache_manager=cache, close=cache._cleanup_event_subscriptions)
    with TestClient(create_app("platform-test-token", runtime_factory=lambda: runtime)) as client:
        yield client


def add_platform(client):
    response = client.post("/api/v1/platforms", headers=AUTH, json={
        "preset_id": "custom", "name": "Test provider", "model": "fixed-model",
        "api_url": "https://llm.invalid/v1", "api_key": "fixed-secret",
    })
    assert response.status_code == 201
    return response.json()


def test_platform_endpoints_authenticate_and_preserve_legacy_configuration(client):
    ConfigMixin().save_config({"extension": {"enabled": True}})
    assert client.get("/api/v1/platforms").status_code == 401
    listing = client.get("/api/v1/platforms", headers=AUTH).json()
    PlatformListResponse.model_validate(listing)
    assert listing["platforms"] == []
    assert any(preset["id"] == "custom" for preset in listing["presets"])
    created = add_platform(client)
    platform_id = created["id"]
    assert client.put(f"/api/v1/platforms/{platform_id}", headers=AUTH, json={"name": "Updated"}).json()["api_key"] == "fixed-secret"
    bindings = {"active": platform_id, "extract": None, "translate": platform_id, "polish": None, "proofread": None}
    assert client.put("/api/v1/platforms/bindings", headers=AUTH, json=bindings).json() == bindings
    assert client.delete(f"/api/v1/platforms/{platform_id}", headers=AUTH).json() == {"deleted": True}
    result = client.get("/api/v1/platforms", headers=AUTH).json()
    assert result["platforms"] == []
    assert all(value is None for value in result["bindings"].values())
    assert ConfigMixin().load_config()["extension"] == {"enabled": True}


def test_platform_mutation_notifies_websocket_without_credentials(client):
    with client.websocket_connect("/api/v1/ws?token=platform-test-token") as websocket:
        add_platform(client)
        message = websocket.receive_json()
        assert message["type"] == "platforms.changed"
        assert message["data"] == {}
        assert "fixed-secret" not in str(message)


@pytest.mark.parametrize("patch", [
    {"rpm_limit": -1}, {"rpm_limit": 1.5}, {"temperature": 2.1},
    {"thinking_budget": -2}, {"think_depth": "unsupported"},
    {"extra_headers": {"x-value": 3}}, {"name": None}, {"tag": "overwrite"},
])
def test_platform_validation_does_not_echo_secrets_or_mutate_saved_values(client, patch):
    platform_id = add_platform(client)["id"]
    before = ConfigMixin().load_config()
    patch["api_key"] = "secret-from-rejected-request"
    response = client.put(f"/api/v1/platforms/{platform_id}", headers=AUTH, json=patch)
    assert response.status_code == 422
    assert "secret-from-rejected-request" not in response.text
    assert ConfigMixin().load_config() == before


def test_platform_missing_busy_and_binding_errors_are_stable(client, monkeypatch):
    assert client.delete("/api/v1/platforms/missing", headers=AUTH).json() == {"detail": "platform_not_found"}
    platform_id = add_platform(client)["id"]
    bindings = {"active": "missing", "extract": None, "translate": None, "polish": None, "proofread": None}
    assert client.put("/api/v1/platforms/bindings", headers=AUTH, json=bindings).status_code == 422
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    response = client.delete(f"/api/v1/platforms/{platform_id}", headers=AUTH)
    assert response.status_code == 409
    assert response.json() == {"detail": "operation_busy"}


def test_models_use_service_and_do_not_expose_provider_errors(client, monkeypatch):
    platform_id = add_platform(client)["id"]
    monkeypatch.setattr("ModuleFolders.Application.PlatformService.PlatformService._fetch_models", lambda *args: ["fixed-model"])
    response = client.get(f"/api/v1/platforms/{platform_id}/models", headers=AUTH)
    assert response.json() == {"platform_id": platform_id, "models": ["fixed-model"]}

    def fail(*args):
        raise RuntimeError("upstream credentials: fixed-secret")

    monkeypatch.setattr("ModuleFolders.Application.PlatformService.PlatformService._fetch_models", fail)
    response = client.get(f"/api/v1/platforms/{platform_id}/models", headers=AUTH)
    assert response.status_code == 502
    assert response.json() == {"detail": "model_fetch_failed"}


def test_model_provider_logs_are_redacted_before_websocket_delivery(client, monkeypatch, capsys):
    from ModuleFolders.Log.Log import LogMixin

    platform_id = add_platform(client)["id"]

    def fail(*args):
        error = RuntimeError("provider reflected fixed-secret")
        LogMixin().error("provider rejected fixed-secret", error)
        raise error

    monkeypatch.setattr("ModuleFolders.Application.PlatformService.PlatformService._fetch_models", fail)
    with client.websocket_connect("/api/v1/ws?token=platform-test-token") as websocket:
        assert client.get(f"/api/v1/platforms/{platform_id}/models", headers=AUTH).status_code == 502
        message = websocket.receive_json()
        assert message["type"] == "log"
        assert "fixed-secret" not in str(message)
        assert "REDACTED" in str(message)
    assert "fixed-secret" not in capsys.readouterr().out


def test_platform_test_authenticates_and_returns_counts_without_keys(client, monkeypatch):
    from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester

    platform_id = add_platform(client)["id"]
    monkeypatch.setattr(LLMRequester, "sent_request", lambda *args: (False, "", "fixed", 8, 4))
    assert client.post(f"/api/v1/platforms/{platform_id}/test").status_code == 401
    with client.websocket_connect("/api/v1/ws?token=platform-test-token") as websocket:
        response = client.post(f"/api/v1/platforms/{platform_id}/test", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == {
            "platform_id": platform_id, "success_count": 1, "failure_count": 0,
            "results": [{"key_index": 1, "success": True, "error_code": None}],
        }
        message = websocket.receive_json()
        assert message["type"] == "api.test.done"
        assert message["data"] == response.json()
        assert "fixed-secret" not in response.text + str(message)
        assert client.get("/api/v1/tasks/current", headers=AUTH).json()["status"] == "idle"


def test_openapi_documents_application_and_validation_422_shapes(client):
    document = client.get("/openapi.json", headers=AUTH).json()
    response = document["paths"]["/api/v1/platforms"]["post"]["responses"]["422"]["content"]["application/json"]["schema"]
    assert {entry["$ref"] for entry in response["anyOf"]} == {
        "#/components/schemas/ErrorResponse", "#/components/schemas/ValidationErrorResponse",
    }
    issue = document["components"]["schemas"]["ValidationIssue"]
    assert set(issue["required"]) == {"loc", "msg", "type"}
