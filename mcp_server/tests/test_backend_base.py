import pytest

from ainiee_mcp.backend.base import AiNieeBackend
from ainiee_mcp.backend.models import (
    AnalysisResult,
    ApiTestResult,
    CacheItemView,
    GlossaryResult,
    TaskStatus,
)


def test_abc_not_instantiable():
    with pytest.raises(TypeError):
        AiNieeBackend()


def test_complete_subclass_instantiable():
    class Dummy(AiNieeBackend):
        def ping(self): return True
        def get_status(self): return TaskStatus()
        def start_task(self, mode, continue_=False, input_folder=None, output_folder=None): return {}
        def stop_task(self): return {}
        def load_project(self, translation_project=None, input_folder=None, exclude_rule=None): return {}
        def start_analysis(self): return {}
        def get_analysis_result(self): return None
        def get_analysis_data(self): return None
        def start_glossary(self): return {}
        def get_glossary_result(self): return None
        def test_api(self, tag): return {}
        def get_apitest_result(self): return None
        def export(self, export_path): return {}
        def save_cache(self): return {}
        def cache_search(self, query, scope="all", regex=False, flagged_only=False, limit=200): return []
        def cache_stats(self): return {}
        def cache_update(self, edits): return {}
        def cache_replace(self, rules, dry_run=True): return {}

    assert Dummy().ping() is True


def test_taskstatus_from_response():
    resp = {
        "app_status": "TASKING", "work_status_code": 1001, "has_project": True,
        "project_id": "p", "project_name": "n",
        "progress": {"total_line": 100, "line": 35, "remaining_line": 65,
                     "percent": 35.0, "is_complete": False, "token": 123},
        "async": {"analysis": {"running": True}},
    }
    s = TaskStatus.from_response(resp)
    assert s.app_status == "TASKING" and s.line == 35 and s.percent == 35.0
    assert s.has_project and s.async_tasks["analysis"]["running"] is True
    assert s.to_dict()["project_name"] == "n"


def test_analysis_from_payload():
    p = {"status": "success",
         "analysis_data": {"characters": [{"x": 1}], "terms": [], "non_translate": [],
                            "stats": {"character_count": 1}},
         "message": "ok"}
    a = AnalysisResult.from_payload(p)
    assert a.status == "success" and len(a.characters) == 1 and a.stats["character_count"] == 1


def test_analysis_from_payload_keeps_last_run_at():
    p = {"status": "success",
         "analysis_data": {"characters": [], "terms": [], "non_translate": [],
                           "stats": {}, "last_run_at": "2026-05-18 16:06:28"}}
    a = AnalysisResult.from_payload(p)
    assert a.last_run_at == "2026-05-18 16:06:28"


def test_glossary_and_apitest_from_payload():
    g = GlossaryResult.from_payload(
        {"status": "success", "updated_data": [{"src": "a", "dst": "b"}],
         "success_count": 1, "total_count": 1})
    assert g.success_count == 1 and g.updated_data[0]["dst"] == "b"
    t = ApiTestResult.from_payload({"success": ["k1"], "failure": []})
    assert t.success == ["k1"] and t.failure == []


def test_cacheitemview_from_dict_maps_status_name():
    v = CacheItemView.from_dict(
        {"storage_path": "a.txt", "text_index": 5, "source_text": "hi",
         "translated_text": "你好", "status": 1})
    assert v.text_index == 5 and v.status_name == "translated"
