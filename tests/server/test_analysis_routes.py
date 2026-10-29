import base64
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ModuleFolders.Base.Base import Base
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject
from Server.app import create_app


AUTH = {"Authorization": "Bearer fixed-analysis-token"}
PATH = "/api/v1/projects/current/analysis"


@pytest.fixture
def client():
    manager = CacheManager()
    manager.load_from_project(CacheProject(project_id="analysis-api", project_name="API", input_path="fixture"))
    manager.set_analysis_data({"version": 1, "extension": {"keep": True}, "characters": [{"source": "Alice", "recommended_translation": "爱丽丝", "gender": "女", "unknown": [1, 2]}], "terms": [], "non_translate": []})
    runtime = SimpleNamespace(cache_manager=manager, close=manager._cleanup_event_subscriptions)
    with TestClient(create_app("fixed-analysis-token", runtime_factory=lambda: runtime)) as client:
        yield client


def test_analysis_routes_authenticate_every_operation(client):
    assert client.get(PATH).status_code == 401
    assert client.put(PATH, json={}).status_code == 401
    for operation in ("import", "publish", "move"):
        assert client.post(f"{PATH}/characters/{operation}", json={}).status_code == 401
    assert client.get(f"{PATH}/characters/export").status_code == 401


def test_analysis_get_put_import_export_publish_move_roundtrip(client):
    initial = client.get(PATH, headers=AUTH)
    assert initial.status_code == 200
    document = initial.json()
    assert document["metadata"]["extension"] == {"keep": True}
    assert document["characters"][0]["unknown"] == [1, 2]
    document["characters"][0]["recommended_translation"] = "艾丽斯"
    saved = client.put(PATH, json=document, headers=AUTH)
    assert saved.status_code == 200
    assert saved.json()["characters"][0]["recommended_translation"] == "艾丽斯"
    payload = base64.b64encode(json.dumps([{"source": "Alice", "recommended_translation": "替换", "gender": "女"}, {"source": "Bob", "gender": "男"}], ensure_ascii=False).encode()).decode()
    imported = client.post(f"{PATH}/characters/import", headers=AUTH, json={"project_id": "analysis-api", "content_base64": payload})
    assert imported.status_code == 200
    assert imported.json()["added"] == imported.json()["replaced"] == 1
    download = client.get(f"{PATH}/characters/export", params={"category": "女", "q": "alice", "project_id": "analysis-api"}, headers=AUTH).json()
    rows = json.loads(base64.b64decode(download["content_base64"]))
    assert len(rows) == 1
    assert rows[0]["recommended_translation"] == "替换"
    assert "unknown" not in rows[0]
    published = client.post(f"{PATH}/characters/publish", headers=AUTH, json={"project_id": "analysis-api", "identities": ["Alice"]})
    assert published.status_code == 200
    assert published.json()["added"] == 1
    assert published.json()["collection"]["tables"][0]["rows"][0]["src"] == "Alice"
    moved = client.post(f"{PATH}/characters/move", headers=AUTH, json={"project_id": "analysis-api", "target": "terms", "category": "Identity", "identities": ["Alice"]})
    assert moved.status_code == 200
    assert [row["source"] for row in moved.json()["characters"]] == ["Bob"]
    assert moved.json()["terms"][0]["source"] == "Alice"
    assert moved.json()["terms"][0]["category_path"] == "Identity"


def test_analysis_validation_conflicts_and_errors_are_explicit(client, monkeypatch):
    assert client.put(PATH, json={"project_id": "analysis-api"}, headers=AUTH).status_code == 422
    assert client.get(f"{PATH}/missing/export", headers=AUTH).status_code == 422
    bad_import = client.post(f"{PATH}/terms/import", json={"project_id": "analysis-api", "content_base64": "***"}, headers=AUTH)
    assert bad_import.status_code == 400
    assert bad_import.json() == {"detail": "analysis_import_invalid"}
    document = client.get(PATH, headers=AUTH).json()
    document["project_id"] = "wrong-project"
    assert client.put(PATH, json=document, headers=AUTH).json() == {"detail": "project_changed"}
    assert client.get(f"{PATH}/characters/export", params={"project_id": "wrong-project"}, headers=AUTH).status_code == 409
    assert client.post(f"{PATH}/non_translate/move", json={"project_id": "analysis-api", "target": "terms", "identities": []}, headers=AUTH).status_code == 400
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    document["project_id"] = "analysis-api"
    busy = client.put(PATH, json=document, headers=AUTH)
    assert busy.status_code == 409
    assert busy.json() == {"detail": "operation_busy"}
