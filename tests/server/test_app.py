import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ModuleFolders.Application.UpdateService import UpdateCheckError
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from Server.app import DEV_ORIGINS, create_app
from Server.deps import get_update_service


TOKEN = "fixed-local-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class RuntimeStub:
    closed = False

    def __init__(self):
        from ModuleFolders.Service.Cache.CacheManager import CacheManager
        self.cache_manager = CacheManager()

    def close(self):
        self.closed = True
        self.cache_manager._cleanup_event_subscriptions()


@pytest.fixture
def app():
    return create_app(TOKEN, runtime_factory=RuntimeStub)


def test_only_health_is_public_including_unknown_and_schema_routes(app):
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        for path in ("/api/v1/version", "/api/v1/config", "/openapi.json", "/missing", "/docs"):
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
            assert client.get(path + "?token=" + TOKEN).status_code == 401
        assert client.post("/health").status_code == 401
        assert client.get("/api/v1/version", headers=AUTH).json()["version"] == "AiNiee 7.2.6"
        assert client.get("/missing", headers=AUTH).status_code == 404
        assert client.get("/openapi.json", headers=AUTH).status_code == 200


def test_duplicate_authorization_headers_fail_closed(app):
    with TestClient(app) as client:
        response = client.get("/api/v1/config", headers=[("Authorization", "Bearer " + TOKEN)] * 2)
        assert response.status_code == 401


def test_cors_allows_only_explicit_origins_and_preflight_exception(app):
    with TestClient(app) as client:
        headers = {
            "Origin": DEV_ORIGINS[0],
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        response = client.options("/api/v1/config", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == DEV_ORIGINS[0]
        assert client.options("/api/v1/config", headers={"Origin": DEV_ORIGINS[0]}).status_code == 401
        assert client.get("/api/v1/config", headers={"Origin": DEV_ORIGINS[0]}).status_code == 401
        for origin in ("https://evil.example", "null", "http://localhost:5173.evil.example"):
            assert client.options("/api/v1/config", headers={**headers, "Origin": origin}).status_code == 403
            assert client.get("/api/v1/config", headers={**AUTH, "Origin": origin}).status_code == 403
        valid = client.get("/api/v1/version", headers={**AUTH, "Origin": DEV_ORIGINS[1]})
        assert valid.headers["access-control-allow-origin"] == DEV_ORIGINS[1]


def test_config_patch_persists_across_app_restart_and_preserves_unknown_keys(app, isolated_app_paths):
    with TestClient(app) as client:
        first = client.patch("/api/v1/config", json={"accent_color": "#808b9d", "extension": {"old": True}}, headers=AUTH)
        assert first.status_code == 200
        response = client.patch("/api/v1/config", json={"accent_color": "#123456"}, headers=AUTH)
        assert response.json()["extension"] == {"old": True}
        for invalid in ([], "text", 42, None):
            assert client.patch("/api/v1/config", content=json.dumps(invalid), headers={**AUTH, "Content-Type": "application/json"}).status_code == 422
        for value in ("NaN", "Infinity", "-Infinity"):
            invalid = client.patch(
                "/api/v1/config", content='{"nested":{"value":' + value + '}}',
                headers={**AUTH, "Content-Type": "application/json"},
            )
            assert invalid.status_code == 422
            assert "input" not in invalid.json()["detail"][0]
    persisted = json.loads((isolated_app_paths / "data" / "config.json").read_text(encoding="utf-8"))
    assert persisted["accent_color"] == "#123456"
    assert "nested" not in persisted
    with TestClient(create_app(TOKEN, runtime_factory=RuntimeStub)) as restarted:
        config = restarted.get("/api/v1/config", headers=AUTH).json()
        assert config["accent_color"] == "#123456"
        assert config["extension"] == {"old": True}


@pytest.mark.parametrize("path,headers", [
    ("/api/v1/ws", {}),
    ("/api/v1/ws?token=wrong", {}),
    (f"/api/v1/ws?token={TOKEN}&token={TOKEN}", {}),
    (f"/api/v1/ws?token={TOKEN}", {"Origin": "https://evil.example"}),
    ("/not-a-websocket", {}),
])
def test_websocket_rejects_missing_invalid_or_ambiguous_credentials(app, path, headers):
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(path, headers=headers):
                pass
        assert error.value.code == 1008


def test_worker_event_reaches_websocket_within_200ms(app):
    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/ws?token={TOKEN}", headers={"Origin": DEV_ORIGINS[0]}) as websocket:
            started = time.monotonic()
            worker = threading.Thread(target=EventManager.get_singleton().emit, args=(Base.EVENT.TASK_UPDATE, {"line": 7}))
            worker.start()
            message = websocket.receive_json()
            elapsed = time.monotonic() - started
            worker.join(timeout=1)
            assert not worker.is_alive()
            assert message["type"] == "task.update"
            assert message["data"] == {"line": 7}
            assert message["seq"] >= 1 and message["ts"] > 0
            assert elapsed < 0.2, f"WebSocket delivery took {elapsed:.3f}s"


def test_runtime_is_created_once_and_closed_with_all_bridge_subscriptions_removed():
    runtimes = []
    before = EventManager.get_singleton().event_callbacks

    def factory():
        runtime = RuntimeStub()
        runtimes.append(runtime)
        return runtime

    app = create_app(TOKEN, runtime_factory=factory)
    assert not runtimes
    with TestClient(app) as client:
        client.get("/health")
        client.get("/health")
        assert len(runtimes) == 1 and not runtimes[0].closed
    assert runtimes[0].closed
    assert EventManager.get_singleton().event_callbacks == before


def test_shutdown_forwards_to_injected_callback_once():
    calls = []
    app = create_app(TOKEN, runtime_factory=RuntimeStub, shutdown_callback=lambda: calls.append("shutdown"))
    with TestClient(app) as client:
        assert client.post("/api/v1/shutdown").status_code == 401
        response = client.post("/api/v1/shutdown", headers=AUTH)
        assert response.status_code == 202
        assert response.json() == {"status": "shutting_down"}
        assert calls == ["shutdown"]


def test_update_check_uses_injected_service_and_maps_failures(app):
    result = {"current_version": "7.2.6", "latest_version": "7.3.0", "update_available": True, "release_url": "https://example.invalid/release"}

    class Updates:
        def check(self):
            return result

    class FailedUpdates:
        def check(self):
            raise UpdateCheckError("Unable to reach the update source")

    app.dependency_overrides[get_update_service] = Updates
    with TestClient(app) as client:
        assert client.get("/api/v1/update/check", headers=AUTH).json() == result
        app.dependency_overrides[get_update_service] = FailedUpdates
        assert client.get("/api/v1/update/check", headers=AUTH).status_code == 502


def test_exported_openapi_matches_backend_and_includes_websocket_contract(app):
    schema = app.openapi()
    exported = json.loads((Path(__file__).resolve().parents[2] / "openapi.json").read_text(encoding="utf-8"))
    assert schema == exported
    assert schema["paths"]["/api/v1/config"]["patch"]["security"] == [{"BearerToken": []}]
    assert "security" not in schema["paths"]["/health"]["get"]
    assert "WebSocketMessage" in schema["components"]["schemas"]
    assert schema["x-websocket"]["path"] == "/api/v1/ws"
    assert TOKEN not in json.dumps(schema)
