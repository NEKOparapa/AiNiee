from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ModuleFolders.Base.Base import Base
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject
from Server.app import create_app


AUTH = {"Authorization": "Bearer fixed-project-test-token"}


class FixedReader:
    def get_support_project_types(self):
        return ["AutoType", "Txt"]

    def read_files(self, project_type, path, exclude):
        return CacheProject(
            project_id="server-fixture", project_name="Server fixture", project_type=project_type,
            input_path=path, files={"chapter/a.txt": CacheFile(
                storage_path="chapter/a.txt", file_project_type="Txt",
                items=[CacheItem(text_index=1, source_text="Fixed source")],
            )},
        )


@pytest.fixture
def client():
    manager = CacheManager()
    runtime = SimpleNamespace(
        cache_manager=manager, file_reader=FixedReader(), close=manager._cleanup_event_subscriptions,
    )
    with TestClient(create_app("fixed-project-test-token", runtime_factory=lambda: runtime)) as client:
        yield client


def test_project_routes_are_authenticated(client):
    for path in ("current", "history", "current/files", "current/stats"):
        assert client.get("/api/v1/projects/" + path).status_code == 401
    assert client.post("/api/v1/projects/open", json={"path": "any"}).status_code == 401
    assert client.delete("/api/v1/projects/history/fixture").status_code == 401
    assert client.post("/api/v1/fs/list", json={"path": "any"}).status_code == 401


def test_open_current_files_stats_and_directory_flow(client, tmp_path):
    initial = client.get("/api/v1/projects/current", headers=AUTH).json()
    assert initial["project"] is None
    assert initial["supported_project_types"] == ["AutoType", "Txt"]
    assert client.patch("/api/v1/config", headers=AUTH, json={"translation_project": "Txt"}).status_code == 200
    opened = client.post("/api/v1/projects/open", headers=AUTH, json={"path": str(tmp_path)})
    assert opened.status_code == 200
    assert opened.json()["project_id"] == "server-fixture"
    assert opened.json()["item_count"] == 1
    current = client.get("/api/v1/projects/current", headers=AUTH).json()
    assert current["project"] == opened.json()
    assert current["configured_path"] == str(tmp_path)
    assert current["selected_project_type"] == "Txt"
    assert client.get("/api/v1/projects/current/files", headers=AUTH).json()[0]["path"] == "chapter/a.txt"
    assert client.get("/api/v1/projects/current/stats", headers=AUTH).json()["untranslated"] == 1
    listing = client.post("/api/v1/fs/list", headers=AUTH, json={"path": str(tmp_path)})
    assert listing.status_code == 200
    assert listing.json()["path"] == str(tmp_path)


def test_open_rejects_invalid_parameters_and_returns_safe_business_errors(client, tmp_path, monkeypatch):
    for body in ({}, {"path": ""}, {"path": 42}, {"path": "test", "unknown": True}):
        assert client.post("/api/v1/projects/open", headers=AUTH, json=body).status_code == 422
    missing = client.post("/api/v1/projects/open", headers=AUTH, json={"path": str(tmp_path / "missing")})
    assert missing.status_code == 404
    assert missing.json() == {"detail": "project_path_not_found"}
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    busy = client.post("/api/v1/projects/open", headers=AUTH, json={"path": str(tmp_path)})
    assert busy.status_code == 409
    assert busy.json() == {"detail": "operation_busy"}


def test_project_stats_and_files_without_project_are_explicit(client):
    for path in ("files", "stats"):
        response = client.get("/api/v1/projects/current/" + path, headers=AUTH)
        assert response.status_code == 409
        assert response.json() == {"detail": "project_not_open"}


def test_history_load_and_delete_contracts_preserve_current_project(client, tmp_path):
    assert client.get("/api/v1/projects/history", headers=AUTH).json() == []
    client.post("/api/v1/projects/open", headers=AUTH, json={"path": str(tmp_path)})
    history = client.get("/api/v1/projects/history", headers=AUTH).json()
    assert len(history) == 1
    assert history[0]["project_id"] == "server-fixture"
    reopened = client.post("/api/v1/projects/open", headers=AUTH, json={"path": history[0]["cache_path"]})
    assert reopened.status_code == 200
    assert reopened.json()["project_id"] == "server-fixture"
    blocked = client.delete("/api/v1/projects/history/server-fixture", headers=AUTH)
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "project_history_current"}
    missing = client.delete("/api/v1/projects/history/missing", headers=AUTH)
    assert missing.status_code == 404
