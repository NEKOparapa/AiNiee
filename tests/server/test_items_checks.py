from types import SimpleNamespace
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from ModuleFolders.Application.ConfigService import ConfigService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject, CacheProjectStatistics
from ModuleFolders.Service.TranslationChecker.LanguageChecker import LanguageChecker
from Server.app import create_app


AUTH = {"Authorization": "Bearer fixed-item-check-token"}
FILE = "nested/中文 filename.txt"


@pytest.fixture
def client(monkeypatch):
    manager = CacheManager()
    manager.load_from_project(CacheProject(
        project_id="api-checks", project_name="API checks", project_type="Txt", input_path="fixture",
        stats_data=CacheProjectStatistics(total_line=3, line=2),
        files={FILE: CacheFile(storage_path=FILE, file_project_type="Txt", items=[
            CacheItem(text_index=10, source_text="First source", translated_text="第一条译文", translation_status=1),
            CacheItem(text_index=20, source_text="Second source", translated_text="第二条译文", translation_status=1),
            CacheItem(text_index=40, source_text="Pending source", translation_status=0),
        ])},
    ))
    manager.save_to_file()
    ConfigService().patch_config({"target_language": "chinese_simplified"})
    monkeypatch.setattr(LanguageChecker, "_run_detection", lambda self, items: [[("zh", 1.0)] for _ in items])
    runtime = SimpleNamespace(cache_manager=manager, close=manager._cleanup_event_subscriptions)
    with TestClient(create_app("fixed-item-check-token", runtime_factory=lambda: runtime)) as client:
        yield client


def test_items_checks_require_authentication(client):
    assert client.get("/api/v1/projects/current/items").status_code == 401
    assert client.patch(f"/api/v1/projects/current/items/{quote(FILE, safe='')}/10", json={"translated_text": "edit"}).status_code == 401
    for kind in ("rule", "language", "terminology"):
        assert client.post(f"/api/v1/checks/{kind}", json={}).status_code == 401


def test_item_query_filter_pagination_and_body_validation(client):
    result = client.get("/api/v1/projects/current/items", params={"file": FILE, "status": 1, "page": 2, "size": 1}, headers=AUTH)
    assert result.status_code == 200
    assert result.json()["total"] == 2
    assert result.json()["items"][0]["index"] == 20
    assert result.json()["items"][0]["position"] == 1
    assert client.get("/api/v1/projects/current/items", params={"q": "^Pending", "regex": True}, headers=AUTH).json()["total"] == 1
    for query in ({"size": 1001}, {"page": 0}, {"status": 3}, {"regex": "wrong"}):
        assert client.get("/api/v1/projects/current/items", params=query, headers=AUTH).status_code == 422
    invalid_regex = client.get("/api/v1/projects/current/items", params={"q": "[", "regex": True}, headers=AUTH)
    assert invalid_regex.status_code == 400
    assert invalid_regex.json() == {"detail": "item_regex_invalid"}
    path = f"/api/v1/projects/current/items/{quote(FILE, safe='')}/20"
    for body in ({}, {"translated_text": None}, {"translation_status": 7}, {"source_text": 1}):
        assert client.patch(path, json=body, headers=AUTH).status_code == 422
    edited = client.patch(path, json={"translated_text": "手工译文"}, headers=AUTH)
    assert edited.status_code == 200
    assert edited.json()["translated_text"] == "手工译文"
    assert edited.json()["file"] == FILE
    cleared = client.patch(path, json={"translated_text": ""}, headers=AUTH)
    assert cleared.json()["translation_status"] == 0
    wrong_project = client.patch(path, json={"translated_text": "Must not change", "project_id": "different-project"}, headers=AUTH)
    assert wrong_project.status_code == 409
    assert wrong_project.json() == {"detail": "project_changed"}
    rows = client.get("/api/v1/projects/current/items", headers=AUTH).json()["items"]
    assert rows[1]["translated_text"] == ""


@pytest.mark.parametrize("kind", ["rule", "language", "terminology"])
def test_real_checks_response_contract_and_saved_preferences(client, kind):
    request = {"mode": "report"} if kind == "language" else {}
    result = client.post(f"/api/v1/checks/{kind}", json=request, headers=AUTH)
    assert result.status_code == 200, result.text
    response = result.json()
    assert response["kind"] == kind
    assert response["project_id"] == "api-checks"
    if kind == "rule":
        assert response["issues"][0]["index"] == 40
        assert response["issues"][0]["position"] == 2
    elif kind == "language":
        assert response["reports"][0]["file"] == FILE
        assert response["reports"][0]["stats"] == "zh: 100.00%"
        assert client.get("/api/v1/config", headers=AUTH).json()["check_lang_mode_text"] == "report"
    else:
        assert response["passed"]


def test_checks_validate_options_and_refuse_during_task(client, monkeypatch):
    assert client.post("/api/v1/checks/language", json={"threshold": 2}, headers=AUTH).status_code == 422
    assert client.post("/api/v1/checks/language", json={"chunk_size": 0}, headers=AUTH).status_code == 422
    assert client.post("/api/v1/checks/rule", json={"rules": {"unknown": True}}, headers=AUTH).status_code == 422
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    result = client.post("/api/v1/checks/rule", json={}, headers=AUTH)
    assert result.status_code == 409
    assert result.json() == {"detail": "operation_busy"}
