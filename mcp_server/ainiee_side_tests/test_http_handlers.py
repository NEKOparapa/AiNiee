"""Handler-level tests for the AiNiee-side HttpService changes.

Run with AiNiee's own venv from the repo root (it needs AiNiee's deps):
    ./.venv/bin/python mcp_server/ainiee_side_tests/test_http_handlers.py

Not collected by the MCP server's pytest (lives outside mcp_server/tests/).
"""
import os
import re
import sys
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ModuleFolders.Base.Base import Base
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
from ModuleFolders.Service.HttpService.HttpService import HttpService


# ----------------------------- fakes -----------------------------
class FakeItem:
    def __init__(self, idx, src, dst, status):
        self.text_index = idx
        self.source_text = src
        self.translated_text = dst
        self.translation_status = status


class FakeFile:
    def __init__(self, items):
        self.items = items
        self._by_index = {it.text_index: it for it in items}


class FakeProject:
    def __init__(self, files):
        self.files = files
        self.project_id = "proj1"
        self.project_name = "demo"
        self.stats_data = None

    def get_file(self, sp):
        return self.files.get(sp)


class FakeCacheManager:
    def __init__(self, project):
        self.project = project
        self.saved = 0
        self.analysis = {}

    def get_item_count(self):
        return sum(len(f.items) for f in self.project.files.values())

    def get_item_count_by_status(self, status):
        return sum(1 for f in self.project.files.values()
                   for it in f.items if it.translation_status == status)

    def search_items(self, query, scope, is_regex, flagged):
        fields = ["source_text", "translated_text"] if scope == "all" else [scope]
        match = (lambda t: re.search(query, t)) if is_regex else (lambda t: query in t)
        out = []
        for sp, f in self.project.files.items():
            for idx, it in enumerate(f.items):
                if not query.strip():
                    continue
                for fld in fields:
                    val = getattr(it, fld, None)
                    if val and match(val):
                        out.append((sp, idx + 1, it))
                        break
        return out

    def update_item_text(self, sp, ti, field, new_text):
        it = self.project.get_file(sp)._by_index[ti]
        if field == "source_text":
            it.source_text = new_text
        else:
            it.translated_text = new_text
            it.translation_status = 0 if not (new_text and new_text.strip()) else 1

    def save_to_file(self):
        self.saved += 1

    def get_analysis_data(self):
        return self.analysis


def make_service(items=None, config=None):
    if items is None:
        items = [FakeItem(1, "Hello world", "你好世界", 1),
                 FakeItem(2, "The Mavari ship", "玛瓦里飞船", 1),
                 FakeItem(3, "Untranslated", "", 0)]
    project = FakeProject({"a.txt": FakeFile(items)})
    cm = FakeCacheManager(project)
    svc = HttpService()
    svc.set_dependencies(cm, object())
    emitted = []
    svc.emit = lambda event, data: emitted.append((event, data))
    svc.info = svc.error = svc.warning = lambda *a, **k: None
    cfg = config or {
        "label_input_path": "/in", "label_output_path": "/out",
        "platforms": {"openai_1": {"name": "OpenAI", "api_url": "u", "api_key": "k",
                                   "api_format": "OpenAI", "model": "m"}},
        "prompt_dictionary_data": [{"src": "Mavari", "dst": ""}],
    }
    svc.load_config = lambda: dict(cfg)
    svc.save_config = lambda c: cfg.update(c)
    return svc, cm, emitted


# ----------------------------- tests -----------------------------
def test_task_start_translate():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_task_start({"mode": "translate"}, "ip")
    assert code == 200, body
    assert emitted[-1][0] == Base.EVENT.TASK_START
    assert emitted[-1][1] == {"continue_status": False, "current_mode": TaskType.TRANSLATION}
    assert body["input_folder"] == "/in"


def test_task_start_polish_and_continue():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_task_start({"mode": "polish", "continue": True}, "ip")
    assert code == 200
    assert emitted[-1][1] == {"continue_status": True, "current_mode": TaskType.POLISH}


def test_task_start_busy():
    Base.work_status = Base.STATUS.TASKING
    svc, cm, emitted = make_service()
    body, code = svc._h_task_start({"mode": "translate"}, "ip")
    assert code == 409 and body["code"] == "busy"
    assert not emitted


def test_translate_get_alias():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_translate_get({}, "ip")
    assert code == 200 and emitted[-1][1]["current_mode"] == TaskType.TRANSLATION


def test_stop():
    svc, cm, emitted = make_service()
    body, code = svc._h_stop({}, "ip")
    assert code == 200 and emitted[-1][0] == Base.EVENT.TASK_STOP


def test_status_has_async():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_status({}, "ip")
    assert code == 200 and body["has_project"] is True
    assert set(body["async"]) == {"analysis", "glossary", "apitest"}


def test_analysis_start_and_result_cycle():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_analysis_start({}, "ip")
    assert code == 202 and emitted[-1][0] == Base.EVENT.ANALYSIS_TASK_START
    # pending before DONE
    rbody, rcode = svc._result_response("analysis")
    assert rcode == 202 and rbody["status"] == "pending"
    # simulate DONE
    svc._on_analysis_done(Base.EVENT.ANALYSIS_TASK_DONE,
                          {"status": "success", "analysis_data": {"characters": [{"n": "A"}]},
                           "message": "ok"})
    rbody, rcode = svc._result_response("analysis")
    assert rcode == 200 and rbody["has_result"] is True
    assert rbody["result"]["analysis_data"]["characters"][0]["n"] == "A"


def test_analysis_requires_idle():
    Base.work_status = Base.STATUS.TASKING
    svc, cm, emitted = make_service()
    body, code = svc._h_analysis_start({}, "ip")
    assert code == 409


def test_analysis_data_returns_persisted_tables():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    cm.analysis = {"status": "success", "last_run_at": "2026-05-18 16:06:28",
                   "characters": [{"source": "Arden"}], "terms": [{"source": "flux"}],
                   "non_translate": [], "stats": {"character_count": 1}}
    body, code = svc._h_analysis_data({}, "ip")
    assert code == 200 and body["has_analysis"] is True
    assert body["analysis_data"]["characters"][0]["source"] == "Arden"
    assert body["analysis_data"]["last_run_at"] == "2026-05-18 16:06:28"


def test_analysis_data_empty_when_no_saved_data():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    cm.analysis = {}
    body, code = svc._h_analysis_data({}, "ip")
    assert code == 200 and body["has_analysis"] is False and body["analysis_data"] == {}


def test_analysis_data_no_project():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service(items=[])  # empty project -> no_project guard
    body, code = svc._h_analysis_data({}, "ip")
    assert code == 409 and body["code"] == "no_project"


def test_glossary_translate():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_glossary_translate({}, "ip")
    assert code == 202 and emitted[-1][0] == Base.EVENT.GLOSS_TASK_START
    assert emitted[-1][1]["prompt_dictionary_data"][0]["src"] == "Mavari"


def test_glossary_empty_400():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service(config={"prompt_dictionary_data": []})
    body, code = svc._h_glossary_translate({}, "ip")
    assert code == 400


def test_apitest_loads_platform():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_apitest({"tag": "openai_1"}, "ip")
    assert code == 202 and emitted[-1][0] == Base.EVENT.API_TEST_START
    assert emitted[-1][1]["api_key"] == "k" and emitted[-1][1]["tag"] == "openai_1"


def test_apitest_bad_tag():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_apitest({"tag": "nope"}, "ip")
    assert code == 400 and "available_tags" in body


def test_cache_search():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_cache_search({"query": "Mavari", "scope": "source_text"}, "ip")
    assert code == 200 and body["count"] == 1
    assert body["items"][0]["text_index"] == 2


def test_cache_stats():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_cache_stats({}, "ip")
    assert code == 200 and body["total"] == 3 and body["translated"] == 2 and body["untranslated"] == 1


def test_cache_update_applies_and_saves():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_cache_update(
        {"edits": [{"storage_path": "a.txt", "text_index": 1,
                    "field": "translated_text", "new_text": "改好的译文"}]}, "ip")
    assert code == 200 and body["updated"] == 1 and not body["failed"]
    assert cm.project.get_file("a.txt")._by_index[1].translated_text == "改好的译文"
    assert cm.saved == 1


def test_cache_update_busy_blocks():
    Base.work_status = Base.STATUS.TASKING
    svc, cm, emitted = make_service()
    body, code = svc._h_cache_update({"edits": []}, "ip")
    assert code == 409 and body["code"] == "busy"


def test_cache_update_bad_file():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_cache_update(
        {"edits": [{"storage_path": "missing.txt", "text_index": 1,
                    "field": "translated_text", "new_text": "x"}]}, "ip")
    assert code == 200 and body["updated"] == 0 and len(body["failed"]) == 1


def test_cache_replace_dry_run_then_apply():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    rules = [{"find": "玛瓦里", "replace": "玛瓦丽"}]
    body, code = svc._h_cache_replace({"rules": rules, "dry_run": True}, "ip")
    assert code == 200 and body["matched_items"] == 1 and body["applied"] == 0
    # unchanged after dry run
    assert cm.project.get_file("a.txt")._by_index[2].translated_text == "玛瓦里飞船"
    # apply
    body, code = svc._h_cache_replace({"rules": rules, "dry_run": False}, "ip")
    assert code == 200 and body["applied"] == 1
    assert cm.project.get_file("a.txt")._by_index[2].translated_text == "玛瓦丽飞船"
    assert cm.saved == 1


def test_cache_replace_source_guard():
    Base.work_status = Base.STATUS.IDLE
    # translated has "船" in two items, but source_requires only matches the Mavari item
    items = [FakeItem(1, "Hello world", "测试船只", 1),
             FakeItem(2, "The Mavari ship", "玛瓦里船", 1)]
    svc, cm, emitted = make_service(items=items)
    rules = [{"find": "船", "replace": "舰", "source_requires": "Mavari"}]
    body, code = svc._h_cache_replace({"rules": rules, "dry_run": False}, "ip")
    assert code == 200 and body["applied"] == 1
    assert cm.project.get_file("a.txt")._by_index[1].translated_text == "测试船只"  # guarded out
    assert cm.project.get_file("a.txt")._by_index[2].translated_text == "玛瓦里舰"


def test_cache_replace_skip_if_followed_by():
    Base.work_status = Base.STATUS.IDLE
    items = [FakeItem(1, "space", "空间站", 1), FakeItem(2, "space", "空间", 1)]
    svc, cm, emitted = make_service(items=items)
    # replace 空间 -> 星域 but skip when followed by 站
    rules = [{"find": "空间", "replace": "星域", "skip_if_followed_by": ["站"]}]
    body, code = svc._h_cache_replace({"rules": rules, "dry_run": False}, "ip")
    assert cm.project.get_file("a.txt")._by_index[1].translated_text == "空间站"  # skipped
    assert cm.project.get_file("a.txt")._by_index[2].translated_text == "星域"


def test_cache_replace_source_excludes_negative_guard():
    Base.work_status = Base.STATUS.IDLE
    items = [FakeItem(1, "Lieutenant Toren reported", "Toren上尉报告", 1),
             FakeItem(2, "Toren reported", "Toren上尉报告", 1)]
    svc, cm, emitted = make_service(items=items)
    rules = [{"find": r"(?<![A-Za-z])(Toren)[\s　]*上尉", "replace": r"\1", "regex": True,
              "source_requires": ["(?<![A-Za-z])Toren"],
              "source_excludes": ["(?i)(?<![A-Za-z])Lieutenant"]}]
    body, code = svc._h_cache_replace({"rules": rules, "dry_run": False}, "ip")
    assert code == 200 and body["applied"] == 1
    # source has 'Lieutenant' -> excluded, rank kept
    assert cm.project.get_file("a.txt")._by_index[1].translated_text == "Toren上尉报告"
    # source lacks the rank -> hallucinated rank removed
    assert cm.project.get_file("a.txt")._by_index[2].translated_text == "Toren报告"


def test_cache_replace_source_requires_list_or():
    Base.work_status = Base.STATUS.IDLE
    items = [FakeItem(1, "Mavari ship", "玛瓦里船", 1), FakeItem(2, "random text", "玛瓦里船", 1)]
    svc, cm, emitted = make_service(items=items)
    rules = [{"find": "玛瓦里", "replace": "Mavari", "source_requires": ["Mavari", "Velmora"]}]
    svc._h_cache_replace({"rules": rules, "dry_run": False}, "ip")
    assert cm.project.get_file("a.txt")._by_index[1].translated_text == "Mavari船"  # source has Mavari
    assert cm.project.get_file("a.txt")._by_index[2].translated_text == "玛瓦里船"     # matches neither


def test_cache_replace_scope_source_text():
    Base.work_status = Base.STATUS.IDLE
    items = [FakeItem(1, "The Mavari ship", "玛瓦里飞船", 1)]
    svc, cm, emitted = make_service(items=items)
    rules = [{"find": "Mavari", "replace": "Arden", "scope": "source_text"}]
    body, code = svc._h_cache_replace({"rules": rules, "dry_run": False}, "ip")
    assert code == 200 and body["applied"] == 1
    it = cm.project.get_file("a.txt")._by_index[1]
    assert it.source_text == "The Arden ship"   # source rewritten
    assert it.translated_text == "玛瓦里飞船"     # translated left untouched
    assert body["changed_preview"][0]["field"] == "source_text"


def test_cache_replace_scope_all_hits_both_fields():
    Base.work_status = Base.STATUS.IDLE
    items = [FakeItem(1, "warp core", "warp 核心", 1)]
    svc, cm, emitted = make_service(items=items)
    rules = [{"find": "warp", "replace": "flux", "scope": "all"}]
    body, code = svc._h_cache_replace({"rules": rules, "dry_run": False}, "ip")
    assert code == 200 and body["applied"] == 2   # both fields written
    it = cm.project.get_file("a.txt")._by_index[1]
    assert it.source_text == "flux core"
    assert it.translated_text == "flux 核心"


def test_cache_replace_invalid_scope_400():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    rules = [{"find": "x", "replace": "y", "scope": "bogus"}]
    body, code = svc._h_cache_replace({"rules": rules, "dry_run": False}, "ip")
    assert code == 400


def test_export_and_cache_save_guards():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    body, code = svc._h_export({"export_path": "/out"}, "ip")
    assert code == 200 and emitted[-1][0] == Base.EVENT.TASK_MANUAL_EXPORT
    body, code = svc._h_export({}, "ip")
    assert code == 400  # missing export_path
    body, code = svc._h_cache_save({}, "ip")
    assert emitted[-1][0] == Base.EVENT.TASK_MANUAL_SAVE_CACHE


def test_project_load_no_deps():
    Base.work_status = Base.STATUS.IDLE
    svc, cm, emitted = make_service()
    svc.file_reader = None  # simulate not ready
    body, code = svc._h_project_load({}, "ip")
    assert code == 503


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception:
            failed += 1
            print(f"FAIL: {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed (of {len(tests)})")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
