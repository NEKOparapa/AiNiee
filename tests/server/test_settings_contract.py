from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ModuleFolders.Base.Base import Base
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject, CacheProjectStatistics
from Server.app import create_app
from Server.schemas.config import ConfigDocument, ConfigPatch


AUTH = {"Authorization": "Bearer settings-test-token"}


@pytest.fixture
def runtime():
    cache = CacheManager()
    runtime = SimpleNamespace(cache_manager=cache, close=cache._cleanup_event_subscriptions)
    yield runtime
    cache._cleanup_event_subscriptions()


@pytest.fixture
def client(runtime):
    with TestClient(create_app("settings-test-token", runtime_factory=lambda: runtime)) as client:
        yield client


def test_settings_schema_is_required_for_response_and_optional_for_patch():
    response = ConfigDocument.model_json_schema()
    patch = ConfigPatch.model_json_schema()
    assert "lines_limit" in response["required"]
    assert "response_check_switch" in response["required"]
    assert not patch.get("required")
    assert "default" not in patch["properties"]["lines_limit"]
    assert patch["properties"]["lines_limit"]["type"] == "integer"
    assert ConfigPatch.model_validate({"theme": "dark"}).model_dump(exclude_unset=True) == {"theme": "dark"}


def test_settings_get_and_partial_patch_preserve_other_controls(client):
    initial = client.get("/api/v1/config", headers=AUTH).json()
    assert initial["user_thread_counts"] == 0
    assert initial["response_check_switch"]["return_to_original_text_check"] is True
    client.patch("/api/v1/config", headers=AUTH, json={"lines_limit": 27, "theme": "dark"})
    result = client.patch("/api/v1/config", headers=AUTH, json={"request_timeout": 90}).json()
    assert result["lines_limit"] == 27
    assert result["theme"] == "dark"
    assert result["request_timeout"] == 90
    assert result["tokens_limit"] == initial["tokens_limit"]


@pytest.mark.parametrize("patch", [
    {"lines_limit": -1}, {"tokens_limit": 10000000}, {"user_thread_counts": 1.5},
    {"request_timeout": "10"}, {"lines_limit": None}, {"extract_task_token_limit": 0},
    {"theme": "sepia"}, {"accent_color": "red"}, {"opencc_preset": "unknown"},
    {"response_check_switch": {"reply_format_check": True}},
])
def test_invalid_setting_values_are_rejected_without_changing_config(client, patch):
    before = client.get("/api/v1/config", headers=AUTH).json()
    assert client.patch("/api/v1/config", headers=AUTH, json=patch).status_code == 422
    assert client.get("/api/v1/config", headers=AUTH).json() == before


def test_current_task_is_authenticated_and_returns_real_snapshot(client, runtime, monkeypatch):
    assert client.get("/api/v1/tasks/current").status_code == 401
    assert client.get("/api/v1/tasks/current", headers=AUTH).json() == {
        "status": "idle", "project_id": None, "project_name": None, "progress": {},
    }
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKSTOPPED)
    runtime.cache_manager.project = CacheProject(
        project_id="known-project", project_name="Saved progress",
        stats_data=CacheProjectStatistics(total_line=10, line=4, token=55),
    )
    response = client.get("/api/v1/tasks/current", headers=AUTH).json()
    assert response["status"] == "stopped"
    assert response["project_id"] == "known-project"
    assert response["progress"]["line"] == 4
    assert response["progress"]["token"] == 55
