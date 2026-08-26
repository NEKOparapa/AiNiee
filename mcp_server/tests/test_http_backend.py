import httpx
import pytest
import respx

from ainiee_mcp.backend import get_backend
from ainiee_mcp.backend.http_backend import HttpBackend
from ainiee_mcp.errors import AiNieeBusy, AiNieeUnavailable, NoProjectLoaded, ValidationError

BASE = "http://127.0.0.1:3388"


def _backend():
    return HttpBackend(base_url=BASE, timeout=5)


@respx.mock
def test_get_status_parses():
    respx.get(f"{BASE}/api/status").mock(return_value=httpx.Response(200, json={
        "status": "success", "app_status": "TASKING", "work_status_code": 1001,
        "has_project": True, "project_id": "p1", "project_name": "demo",
        "progress": {"total_line": 100, "line": 40, "remaining_line": 60,
                     "percent": 40.0, "is_complete": False, "token": 999},
        "async": {"analysis": {"running": False, "seq": 0}},
    }))
    s = _backend().get_status()
    assert s.app_status == "TASKING" and s.line == 40 and s.project_name == "demo"


@respx.mock
def test_start_task_sends_body():
    route = respx.post(f"{BASE}/api/task/start").mock(
        return_value=httpx.Response(200, json={"status": "success", "mode": "translate"}))
    out = _backend().start_task("translate", continue_=True, input_folder="/in")
    assert out["status"] == "success"
    sent = route.calls.last.request
    import json
    body = json.loads(sent.content)
    assert body["mode"] == "translate" and body["continue"] is True and body["input_folder"] == "/in"
    assert "output_folder" not in body  # None dropped


@respx.mock
def test_busy_409_maps_to_AiNieeBusy():
    respx.post(f"{BASE}/api/task/start").mock(return_value=httpx.Response(
        409, json={"status": "error", "code": "busy", "message": "App is busy"}))
    with pytest.raises(AiNieeBusy):
        _backend().start_task("translate")


@respx.mock
def test_connection_error_maps_to_unavailable():
    respx.get(f"{BASE}/api/status").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(AiNieeUnavailable):
        _backend().get_status()


@respx.mock
def test_ping_false_when_down():
    respx.get(f"{BASE}/api/status").mock(side_effect=httpx.ConnectError("refused"))
    assert _backend().ping() is False


@respx.mock
def test_analysis_pending_then_result():
    r = respx.get(f"{BASE}/api/analysis/result")
    r.mock(return_value=httpx.Response(202, json={"status": "pending", "running": True, "has_result": False}))
    assert _backend().get_analysis_result() is None

    r.mock(return_value=httpx.Response(200, json={
        "status": "success", "has_result": True, "running": False,
        "result": {"status": "success",
                   "analysis_data": {"characters": [{"name": "A"}], "terms": [],
                                     "non_translate": [], "stats": {"character_count": 1}},
                   "message": "done"}}))
    res = _backend().get_analysis_result()
    assert res is not None and res.characters[0]["name"] == "A"


@respx.mock
def test_get_analysis_data_returns_persisted_tables():
    respx.get(f"{BASE}/api/analysis/data").mock(return_value=httpx.Response(200, json={
        "status": "success", "has_analysis": True,
        "analysis_data": {"characters": [{"source": "Arden"}], "terms": [],
                          "non_translate": [], "stats": {"character_count": 1},
                          "last_run_at": "2026-05-18 16:06:28"}}))
    res = _backend().get_analysis_data()
    assert res is not None and res.characters[0]["source"] == "Arden"
    assert res.last_run_at == "2026-05-18 16:06:28"


@respx.mock
def test_get_analysis_data_none_when_no_saved_data():
    respx.get(f"{BASE}/api/analysis/data").mock(return_value=httpx.Response(200, json={
        "status": "success", "has_analysis": False, "analysis_data": {}}))
    assert _backend().get_analysis_data() is None


@respx.mock
def test_get_analysis_data_no_project_raises():
    respx.get(f"{BASE}/api/analysis/data").mock(return_value=httpx.Response(
        409, json={"status": "error", "code": "no_project", "message": "no project"}))
    with pytest.raises(NoProjectLoaded):
        _backend().get_analysis_data()


@respx.mock
def test_glossary_and_apitest_results():
    respx.get(f"{BASE}/api/glossary/result").mock(return_value=httpx.Response(200, json={
        "has_result": True, "result": {"status": "success",
                                        "updated_data": [{"src": "x", "dst": "y"}],
                                        "success_count": 1, "total_count": 1}}))
    g = _backend().get_glossary_result()
    assert g.updated_data[0]["dst"] == "y"

    respx.get(f"{BASE}/api/apitest/result").mock(return_value=httpx.Response(200, json={
        "has_result": True, "result": {"success": ["k1"], "failure": ["k2"]}}))
    t = _backend().get_apitest_result()
    assert t.success == ["k1"] and t.failure == ["k2"]


@respx.mock
def test_cache_search_parses_items():
    respx.post(f"{BASE}/api/cache/search").mock(return_value=httpx.Response(200, json={
        "status": "success", "items": [
            {"storage_path": "a.txt", "text_index": 3, "source_text": "Hi",
             "translated_text": "你好", "status": 1}]}))
    items = _backend().cache_search("Hi")
    assert len(items) == 1 and items[0].text_index == 3 and items[0].status_name == "translated"


@respx.mock
def test_cache_search_no_project_raises():
    respx.post(f"{BASE}/api/cache/search").mock(return_value=httpx.Response(
        409, json={"status": "error", "code": "no_project", "message": "no project"}))
    with pytest.raises(NoProjectLoaded):
        _backend().cache_search("Hi")


@respx.mock
def test_cache_replace_dry_run_body():
    route = respx.post(f"{BASE}/api/cache/replace").mock(
        return_value=httpx.Response(200, json={"status": "success", "changed": []}))
    _backend().cache_replace([{"find": "a", "replace": "b"}], dry_run=True)
    import json
    body = json.loads(route.calls.last.request.content)
    assert body["dry_run"] is True and body["rules"][0]["find"] == "a"


@respx.mock
def test_400_maps_to_validation_error():
    respx.post(f"{BASE}/api/project/load").mock(return_value=httpx.Response(
        400, json={"status": "error", "message": "bad project type"}))
    with pytest.raises(ValidationError):
        _backend().load_project(translation_project="Nope")


def test_get_backend_default(monkeypatch):
    monkeypatch.delenv("AINIEE_MCP_BACKEND", raising=False)
    assert isinstance(get_backend(), HttpBackend)


def test_get_backend_unknown(monkeypatch):
    monkeypatch.setenv("AINIEE_MCP_BACKEND", "weird")
    with pytest.raises(ValueError):
        get_backend()
