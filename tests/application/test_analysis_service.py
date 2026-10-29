import base64
from copy import deepcopy
import json

import pytest

from ModuleFolders.Application.AnalysisService import AnalysisService
from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.TableService import TableService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject


def encoded(rows):
    return base64.b64encode(json.dumps(rows, ensure_ascii=False).encode("utf-8-sig")).decode("ascii")


@pytest.fixture
def manager():
    manager = CacheManager()
    manager.load_from_project(CacheProject(project_id="analysis-fixture", project_name="Fixture", input_path="fixture"))
    manager.set_analysis_data({
        "version": 1, "status": "success", "future_metadata": {"keep": [1, True]},
        "stats": {"legacy_stat": 8},
        "characters": [{"source": "Alice", "recommended_translation": "爱丽丝", "gender": "女", "occurrence_count": 4, "note": "角色", "legacy_row": {"confidence": 0.9}}],
        "terms": [{"source": "World", "recommended_translation": "世界", "category_path": "Place", "occurrence_count": 2, "note": ""}],
        "non_translate": [{"marker": "[tag]", "category": "Tag", "note": "keep"}],
    })
    manager.save_to_file()
    yield manager
    manager._cleanup_event_subscriptions()


def test_analysis_roundtrip_preserves_unknown_metadata_and_cache_shape(manager):
    service = AnalysisService(manager)
    document = service.get()
    assert document["metadata"]["future_metadata"] == {"keep": [1, True]}
    document["metadata"] = {"status": "edited"}
    document["characters"][0].pop("legacy_row")
    document["characters"][0]["recommended_translation"] = "艾丽斯"
    document["terms"] = []
    saved = service.put(document)
    assert saved["characters"][0]["legacy_row"] == {"confidence": 0.9}
    assert saved["metadata"]["future_metadata"] == {"keep": [1, True]}
    assert saved["metadata"]["stats"] == {"legacy_stat": 8, "character_count": 1, "term_count": 0, "non_translate_count": 1, "total_hits": 2}
    cache = CacheManager.read_from_file(CacheManager.get_default_cache_path(project_id="analysis-fixture"))
    analysis = cache.extra[CacheManager.ANALYSIS_EXTRA_KEY]
    assert analysis["status"] == "edited"
    assert "metadata" not in analysis
    assert analysis["characters"][0]["recommended_translation"] == "艾丽斯"


def test_import_replaces_matching_source_last_duplicate_wins_invalid_rows_skipped(manager):
    service = AnalysisService(manager)
    result = service.import_rows("characters", encoded([
        {"source": "Alice", "recommended_translation": "first"},
        {"source": "Alice", "recommended_translation": "last", "occurrence_count": 0, "secret": "discard"},
        {"source": "Bob", "gender": "", "note": "new"},
        {"source": ""}, {"source": ["invalid"]}, 42,
    ]), "analysis-fixture")
    assert (result["added"], result["replaced"], result["skipped"]) == (1, 1, 3)
    rows = result["document"]["characters"]
    assert [row["source"] for row in rows] == ["Alice", "Bob"]
    assert rows[0]["recommended_translation"] == "last"
    assert rows[0]["occurrence_count"] == 1
    assert rows[1]["gender"] == "其他"
    assert "secret" not in rows[0]
    assert "legacy_row" not in rows[0]  # Imports replace the row, as in the desktop UI.
    assert result["document"]["metadata"]["future_metadata"] == {"keep": [1, True]}


def test_export_only_table_fields_and_visible_filters(manager):
    result = AnalysisService(manager).export_rows("characters", category="女", q="alice", project_id="analysis-fixture")
    rows = json.loads(base64.b64decode(result["content_base64"]))
    assert rows == [{"source": "Alice", "recommended_translation": "爱丽丝", "gender": "女", "occurrence_count": 4, "note": "角色"}]
    assert result["media_type"] == "application/json"
    empty = AnalysisService(manager).export_rows("characters", category="missing")
    assert json.loads(base64.b64decode(empty["content_base64"])) == []


def test_publish_uses_glossary_for_characters_and_terms_keeps_existing(manager):
    service = AnalysisService(manager)
    first = service.publish("characters", "analysis-fixture", identities=["Alice"])
    assert first["added"] == 1
    row = next(row for table in first["collection"]["tables"] for row in table["rows"] if row["src"] == "Alice")
    assert row["dst"] == "爱丽丝"
    assert row["info"] == "性别: 女；备注: 角色"
    assert row["regex"] is False
    assert service.publish("characters", "analysis-fixture")["added"] == 0
    assert service.publish("terms", "analysis-fixture")["added"] == 1
    exclusion = service.publish("non_translate", "analysis-fixture")
    assert exclusion["added"] == 1
    assert exclusion["collection"]["tables"][0]["rows"][0]["markers"] == "[tag]"
    assert len(service.get()["characters"]) == 1
    assert TableService().get("characters")["tables"][0]["rows"] == []


def test_cross_table_move_overwrites_target_removes_source_and_preserves_note(manager):
    manager.get_analysis_data()["terms"].append({"source": "Alice", "recommended_translation": "old", "category_path": "Other"})
    service = AnalysisService(manager)
    result = service.move("characters", "analysis-fixture", "terms", "Identity", ["Alice", "Alice", "missing"])
    assert result["characters"] == []
    row = next(row for row in result["terms"] if row["source"] == "Alice")
    assert row["recommended_translation"] == "爱丽丝"
    assert row["note"] == "角色；原分类: 女"
    assert row["category_path"] == "Identity"
    assert row["occurrence_count"] == 4
    reverse = service.move("terms", "analysis-fixture", "characters", "", ["Alice"])
    assert reverse["characters"][0]["gender"] == "其他"
    assert len(reverse["terms"]) == 1
    with pytest.raises(ApplicationError, match="analysis_move_invalid"):
        service.move("non_translate", "analysis-fixture", "terms", "", ["[tag]"])


def test_mutations_check_project_identity_and_busy_state(manager, monkeypatch):
    service = AnalysisService(manager)
    document = service.get()
    document["project_id"] = "different-project"
    with pytest.raises(ApplicationError, match="project_changed"):
        service.put(document)
    with pytest.raises(ApplicationError, match="project_changed"):
        service.import_rows("terms", encoded([{"source": "Extra"}]), "different-project")
    with pytest.raises(ApplicationError, match="project_changed"):
        service.publish("terms", "different-project")
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    with pytest.raises(ApplicationError, match="operation_busy"):
        service.put(service.get())
    with pytest.raises(ApplicationError, match="operation_busy"):
        service.move("terms", "analysis-fixture", "characters", "", ["World"])


def test_analysis_invalid_import_and_failed_save_do_not_change_memory(manager, monkeypatch):
    service = AnalysisService(manager)
    original = deepcopy(manager.get_analysis_data())
    for content in ("invalid-base64", encoded({"wrong": "format"})):
        with pytest.raises(ApplicationError, match="analysis_import_invalid"):
            service.import_rows("terms", content, "analysis-fixture")
    monkeypatch.setattr(manager, "save_to_file", lambda: (_ for _ in ()).throw(OSError("private file path")))
    document = service.get()
    document["characters"] = []
    with pytest.raises(ApplicationError, match="analysis_save_failed"):
        service.put(document)
    assert manager.get_analysis_data() == original
