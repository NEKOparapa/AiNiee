from types import SimpleNamespace
import base64
import json
from io import BytesIO
from zipfile import ZipFile

import openpyxl
from pydantic import ValidationError

import pytest
from fastapi.testclient import TestClient

from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from Server.app import create_app
from Server.schemas.tables import PublicTable, TableMatchOptions, TableRow
from Server.schemas.prompts import PromptUpsertRequest


AUTH = {"Authorization": "Bearer fixed-tables-token"}


@pytest.fixture
def client():
    manager = CacheManager()
    runtime = SimpleNamespace(cache_manager=manager, close=manager._cleanup_event_subscriptions)
    with TestClient(create_app("fixed-tables-token", runtime_factory=lambda: runtime)) as client:
        yield client


def test_table_and_prompt_reads_require_token_and_reject_unknown_kind(client):
    for path in ("/tables/glossary", "/prompts/world", "/prompt-library?kind=system"):
        assert client.get("/api/v1" + path).status_code == 401
        assert client.get("/api/v1" + path, headers=AUTH).status_code == 200
    for path in ("/tables/unknown", "/prompts/unknown", "/prompt-library?kind=unknown"):
        assert client.get("/api/v1" + path, headers=AUTH).status_code == 422


def test_prompt_http_roundtrip_keeps_unknown_row_fields(client):
    data = {"enabled": True, "rows": [{"src": "hello", "dst": "您好", "source_metadata": {"chapter": 3}}]}
    response = client.put("/api/v1/prompts/examples", headers=AUTH, json=data)
    assert response.status_code == 200, response.text
    assert response.json()["rows"][0]["source_metadata"] == {"chapter": 3}
    assert "original_name" not in response.json()["rows"][0]
    assert client.get("/api/v1/prompts/examples", headers=AUTH).json() == response.json()
    assert ConfigMixin().load_config()["translation_example_data"][0]["dst"] == "您好"


def test_prompt_library_exports_integer_preset_ids(client):
    library = client.get("/api/v1/prompt-library", params={"kind": "system"}, headers=AUTH).json()
    assert [prompt["id"] for prompt in library["presets"]] == [100, 200, 400]
    response = client.put("/api/v1/prompts/system", headers=AUTH, json={"selected_id": 200})
    assert response.status_code == 200
    assert response.json()["selected_id"] == 200
    assert client.put("/api/v1/prompts/system", headers=AUTH, json={"selected_id": "missing"}).status_code == 404


def test_table_write_upload_download_and_auth_contract(client):
    payload = {"tables": [{"id": "table-1", "name": "Test", "enabled": True, "rows": [{"src": "Alice", "dst": "爱丽丝", "future": {"keep": True}}]}], "active_table_id": "table-1"}
    assert client.put("/api/v1/tables/glossary", json=payload).status_code == 401
    response = client.put("/api/v1/tables/glossary", json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json()["tables"][0]["rows"][0]["future"] == {"keep": True}
    exported = client.get("/api/v1/tables/glossary/export", params={"format": "xlsx", "bundle": True}, headers=AUTH)
    assert exported.status_code == 200
    request = {"filename": exported.json()["filename"], "content_base64": exported.json()["content_base64"], "preview": True}
    assert client.post("/api/v1/tables/glossary/import", json=request).status_code == 401
    assert client.post("/api/v1/tables/glossary/import", json=request, headers=AUTH).json()["tables"][0]["name"] == "Test"
    assert len(client.get("/api/v1/tables/glossary", headers=AUTH).json()["tables"]) == 1
    imported = client.post("/api/v1/tables/glossary/import", json={**request, "preview": False}, headers=AUTH)
    assert imported.status_code == 200
    assert len(imported.json()["tables"]) == 2
    assert client.put("/api/v1/tables/glossary", json={"tables": [payload["tables"][0]] * 2}, headers=AUTH).status_code == 400


def test_prompt_library_routes_upsert_delete_and_protect_system_presets(client):
    path = "/api/v1/prompt-library?kind=analysis_judgment"
    assert client.post(path, json={"name": "Test", "content": "Fixed"}).status_code == 401
    created = client.post(path, headers=AUTH, json={"name": "Test", "content": "Fixed", "future": 5})
    assert created.status_code == 200, created.text
    identifier = created.json()["selected_id"]
    edited = client.post(path, headers=AUTH, json={"id": identifier, "name": "Edited", "content": "New"})
    assert edited.json()["custom"][0]["future"] == 5
    assert client.delete(path + "&id=30002", headers=AUTH).status_code == 409
    deleted = client.delete(path + "&id=" + identifier, headers=AUTH)
    assert deleted.status_code == 200
    assert deleted.json()["selected_id"] == 30002


@pytest.mark.parametrize("model, fields", [(TableRow, {}), (PublicTable, {"id": "one", "name": "One"}), (TableMatchOptions, {}), (PromptUpsertRequest, {"name": "Name", "content": "Text"})])
def test_document_models_reject_nonfinite_numbers_in_deep_extra_metadata(model, fields):
    with pytest.raises(ValidationError):
        model.model_validate({**fields, "future": {"nested": [float("nan")]}})


@pytest.mark.parametrize("path, method, body", [
    ("/tables/glossary", "put", {"tables": [{"id": "one", "name": "One", "future": {"v": float("nan")}}]}),
    ("/tables/glossary", "put", {"tables": [{"id": "one", "name": "One", "rows": [{"src": "a", "future": [float("inf")]}]}]}),
    ("/tables/glossary", "put", {"tables": [{"id": "one", "name": "One", "match_options": {"future": {"v": float("nan")}}}]}),
    ("/prompt-library?kind=system", "post", {"name": "Bad", "content": "Text", "future": {"v": float("nan")}}),
])
def test_nonfinite_http_payload_cannot_corrupt_config(client, path, method, body):
    before = client.get("/api/v1/config", headers=AUTH).json()
    response = getattr(client, method)("/api/v1" + path, content=json.dumps(body), headers={**AUTH, "Content-Type": "application/json"})
    assert response.status_code == 422
    assert client.get("/api/v1/config", headers=AUTH).json() == before


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_import_rejects_nonfinite_json_before_config_write(client, number):
    raw = '[{"src":"Alice","future":{"nested":[' + number + ']}}]'
    response = client.post("/api/v1/tables/glossary/import", headers=AUTH, json={"filename": "bad.json", "content_base64": base64.b64encode(raw.encode()).decode()})
    assert response.status_code == 400
    assert response.json()["detail"] == "table_import_invalid"
    assert client.get("/api/v1/config", headers=AUTH).status_code == 200


def test_import_rejects_nonfinite_spreadsheet_number(client):
    source = BytesIO()
    workbook = openpyxl.Workbook()
    workbook.active.append(["src", "dst", "info", "regex"])
    workbook.active.append(["Alice", 1, "", False])
    workbook.save(source)
    workbook.close()
    altered = BytesIO()
    with ZipFile(source) as original, ZipFile(altered, "w") as output:
        for entry in original.infolist():
            data = original.read(entry.filename)
            if entry.filename == "xl/worksheets/sheet1.xml":
                assert b"<v>1</v>" in data
                data = data.replace(b"<v>1</v>", b"<v>1e309</v>")
            output.writestr(entry, data)
    response = client.post("/api/v1/tables/glossary/import", headers=AUTH, json={"filename": "bad.xlsx", "content_base64": base64.b64encode(altered.getvalue()).decode()})
    assert response.status_code == 400
    assert client.get("/api/v1/config", headers=AUTH).status_code == 200
