import json
import subprocess
import sys

from mcp.server.fastmcp import FastMCP

from ainiee_mcp.backend.base import AiNieeBackend
from ainiee_mcp.backend.models import AnalysisResult, CacheItemView, TaskStatus
from ainiee_mcp.config_store import ConfigStore
from ainiee_mcp.errors import AiNieeBusy
from ainiee_mcp.tools import register_all

EXPECTED_TOOLS = {
    "ainiee_status", "ainiee_translate", "ainiee_polish", "ainiee_stop", "ainiee_load_project",
    "ainiee_analysis_start", "ainiee_analysis_result", "ainiee_get_analysis",
    "ainiee_glossary_translate",
    "ainiee_glossary_result", "ainiee_api_test", "ainiee_api_test_result", "ainiee_export",
    "ainiee_save_cache",
    "ainiee_get_config", "ainiee_list_platforms", "ainiee_set_platform", "ainiee_set_active_api",
    "ainiee_set_languages", "ainiee_set_io_paths", "ainiee_set_project_type", "ainiee_set_glossary",
    "ainiee_set_exclusions", "ainiee_set_pre_post_replacements", "ainiee_set_characters",
    "ainiee_set_world_style",
    "ainiee_cache_search", "ainiee_cache_stats", "ainiee_cache_update", "ainiee_cache_replace",
}


class FakeBackend(AiNieeBackend):
    def __init__(self):
        self.calls = []
        self.analysis = None
        self.analysis_data = None

    def ping(self): return True
    def get_status(self): return TaskStatus(app_status="IDLE", has_project=True)
    def start_task(self, mode, continue_=False, input_folder=None, output_folder=None):
        self.calls.append(("start_task", mode, continue_, input_folder, output_folder))
        return {"status": "success", "mode": mode}
    def stop_task(self): return {"status": "success"}
    def load_project(self, translation_project=None, input_folder=None, exclude_rule=None):
        self.calls.append(("load_project", translation_project, input_folder, exclude_rule))
        return {"status": "success", "item_count": 5}
    def start_analysis(self): self.calls.append(("start_analysis",)); return {"status": "success"}
    def get_analysis_result(self): return self.analysis
    def get_analysis_data(self): return self.analysis_data
    def start_glossary(self): self.calls.append(("start_glossary",)); return {"status": "success"}
    def get_glossary_result(self): return None
    def test_api(self, tag): self.calls.append(("test_api", tag)); return {"status": "success"}
    def get_apitest_result(self): return None
    def export(self, export_path): self.calls.append(("export", export_path)); return {"status": "success"}
    def save_cache(self): return {"status": "success"}
    def cache_search(self, query, scope="all", regex=False, flagged_only=False, limit=200):
        self.calls.append(("cache_search", query, scope, regex, flagged_only, limit))
        return [CacheItemView("a.txt", 1, "hi", "你好", 1)]
    def cache_stats(self): return {"status": "success", "translated": 5}
    def cache_update(self, edits): self.calls.append(("cache_update", edits)); return {"status": "success"}
    def cache_replace(self, rules, dry_run=True):
        self.calls.append(("cache_replace", rules, dry_run))
        return {"status": "success", "dry_run": dry_run}


def _setup(tmp_path, backend=None):
    backend = backend or FakeBackend()
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"platforms": {"p1": {"name": "A", "api_key": "sek", "model": "m"}},
                               "api_settings": {}}), encoding="utf-8")
    store = ConfigStore(config_path=cfg)
    tools = register_all(FastMCP("test"), backend, store)
    return tools, backend, store


def test_all_tools_registered(tmp_path):
    tools, _, _ = _setup(tmp_path)
    assert set(tools) == EXPECTED_TOOLS


def test_status_serializes(tmp_path):
    tools, _, _ = _setup(tmp_path)
    out = tools["ainiee_status"]()
    assert out["app_status"] == "IDLE" and out["has_project"] is True


def test_translate_dispatch(tmp_path):
    tools, b, _ = _setup(tmp_path)
    tools["ainiee_translate"](continue_=True, input_folder="/in")
    assert ("start_task", "translate", True, "/in", None) in b.calls


def test_analysis_pending_then_result(tmp_path):
    tools, b, _ = _setup(tmp_path)
    assert tools["ainiee_analysis_result"]()["status"] == "pending"
    b.analysis = AnalysisResult(status="success", characters=[{"n": "A"}])
    assert tools["ainiee_analysis_result"]()["characters"][0]["n"] == "A"


def test_get_analysis_empty_when_no_saved_data(tmp_path):
    tools, b, _ = _setup(tmp_path)
    b.analysis_data = None
    out = tools["ainiee_get_analysis"]()
    assert out["status"] == "empty" and out["has_analysis"] is False


def test_get_analysis_returns_persisted_tables(tmp_path):
    tools, b, _ = _setup(tmp_path)
    b.analysis_data = AnalysisResult(status="success", characters=[{"source": "Arden"}],
                                     terms=[{"source": "flux"}], stats={"character_count": 1},
                                     last_run_at="2026-05-18 16:06:28")
    out = tools["ainiee_get_analysis"]()
    assert out["status"] == "success"
    assert out["characters"][0]["source"] == "Arden"
    assert out["terms"][0]["source"] == "flux"
    assert out["last_run_at"] == "2026-05-18 16:06:28"


def test_get_analysis_kind_filter(tmp_path):
    tools, b, _ = _setup(tmp_path)
    b.analysis_data = AnalysisResult(status="success", characters=[{"source": "Arden"}],
                                     terms=[{"source": "flux"}])
    out = tools["ainiee_get_analysis"](kind="terms")
    assert out["kind"] == "terms" and out["value"][0]["source"] == "flux"
    assert "characters" not in out


def test_get_analysis_invalid_kind(tmp_path):
    tools, b, _ = _setup(tmp_path)
    b.analysis_data = AnalysisResult(status="success")
    out = tools["ainiee_get_analysis"](kind="bogus")
    assert out["status"] == "error"


def test_cache_search_serializes_items(tmp_path):
    tools, _, _ = _setup(tmp_path)
    out = tools["ainiee_cache_search"]("hi")
    assert out["count"] == 1 and out["items"][0]["status_name"] == "translated"


def test_cache_replace_defaults_to_dry_run(tmp_path):
    tools, b, _ = _setup(tmp_path)
    tools["ainiee_cache_replace"]([{"find": "a", "replace": "b"}])
    assert ("cache_replace", [{"find": "a", "replace": "b"}], True) in b.calls


def test_set_languages_writes_config(tmp_path):
    tools, _, store = _setup(tmp_path)
    out = tools["ainiee_set_languages"](source="english")
    assert out["status"] == "success" and store.load()["source_language"] == "english"


def test_get_config_redacts_api_key(tmp_path):
    tools, _, _ = _setup(tmp_path)
    out = tools["ainiee_get_config"](section="platforms")
    assert out["value"]["p1"]["api_key"] == "***"


def test_validation_error_returns_error_dict(tmp_path):
    tools, _, _ = _setup(tmp_path)
    out = tools["ainiee_set_languages"](source="martian")
    assert out["status"] == "error" and "allowed" in out["message"]


def test_backend_error_returns_error_dict(tmp_path):
    class Busy(FakeBackend):
        def stop_task(self): raise AiNieeBusy("running")
    tools, _, _ = _setup(tmp_path, backend=Busy())
    out = tools["ainiee_stop"]()
    assert out["status"] == "error"


def test_glossary_translate_writes_terms_first(tmp_path):
    tools, b, store = _setup(tmp_path)
    tools["ainiee_glossary_translate"](terms=[{"src": "a", "dst": ""}])
    assert store.load()["prompt_dictionary_data"][0]["src"] == "a"
    assert ("start_glossary",) in b.calls


def test_tools_module_is_httpx_free():
    code = ("import sys, ainiee_mcp.tools; "
            "assert 'httpx' not in sys.modules, "
            "sorted(m for m in sys.modules if 'httpx' in m)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
