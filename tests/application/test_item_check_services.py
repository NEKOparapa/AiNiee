import json
from copy import deepcopy

import pytest

from ModuleFolders.Application.CheckService import CheckService
from ModuleFolders.Application.ConfigService import ConfigService
from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.ItemService import ItemService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject, CacheProjectStatistics
from ModuleFolders.Service.TranslationChecker.LanguageChecker import LanguageChecker


@pytest.fixture
def manager():
    manager = CacheManager()
    manager.load_from_project(CacheProject(
        project_id="check-fixture", project_name="Checks", project_type="Txt", input_path="input",
        stats_data=CacheProjectStatistics(total_line=4, line=3),
        files={
            "nested/chapter.txt": CacheFile(storage_path="nested/chapter.txt", file_project_type="Txt", items=[
                CacheItem(text_index=10, source_text="Hello 42", translated_text="你好1.2.", translation_status=1),
                CacheItem(text_index=30, source_text="Welcome", translated_text="欢迎", translation_status=2, extra={"language_mismatch_translation": True}),
                CacheItem(text_index=40, source_text="Pending", translated_text="", translation_status=0),
            ]),
            "other.txt": CacheFile(storage_path="other.txt", file_project_type="Txt", items=[
                CacheItem(text_index=50, source_text="Excluded", translated_text="Excluded", translation_status=7),
            ]),
        },
    ))
    manager.save_to_file()
    yield manager
    manager._cleanup_event_subscriptions()


def test_item_filters_and_pagination_preserve_stable_indices(manager):
    service = ItemService(manager)
    response = service.list_items(page=2, size=1)
    assert response["total"] == 4
    assert response["items"][0]["index"] == 30
    assert response["items"][0]["position"] == 1
    assert json.loads(response["items"][0]["id"]) == ["nested/chapter.txt", 30]
    assert [row["index"] for row in service.list_items(file="nested/chapter.txt", status=0)["items"]] == [40]
    assert [row["index"] for row in service.list_items(q="你好")["items"]] == [10]
    assert [row["index"] for row in service.list_items(q=r"^Wel.*", regex=True)["items"]] == [30]
    assert service.list_items(flagged=True)["total"] == 1
    assert service.list_items(flagged=False)["total"] == 3
    assert service.list_items(file="missing")["total"] == 0
    with pytest.raises(ApplicationError, match="item_regex_invalid"):
        service.list_items(q="[", regex=True)


def test_item_edit_uses_original_status_semantics_and_persists(manager):
    service = ItemService(manager)
    edited = service.patch_item("nested/chapter.txt", 30, {"translated_text": "手工修改"})
    assert edited["translation_status"] == TranslationStatus.TRANSLATED
    restored = CacheManager.read_from_file(CacheManager.get_default_cache_path(project_id="check-fixture"))
    assert restored.files["nested/chapter.txt"].get_item(30).translated_text == "手工修改"
    cleared = service.patch_item("nested/chapter.txt", 30, {"translated_text": "  "})
    assert cleared["translation_status"] == TranslationStatus.UNTRANSLATED
    source = service.patch_item("nested/chapter.txt", 30, {"source_text": "New source"})
    assert source["source_text"] == "New source"
    with pytest.raises(ApplicationError, match="item_source_empty"):
        service.patch_item("nested/chapter.txt", 30, {"source_text": " "})
    with pytest.raises(ApplicationError, match="item_not_found"):
        service.patch_item("nested/chapter.txt", 1, {"translated_text": "wrong ordinal"})


def test_write_failure_restores_memory(manager, monkeypatch):
    original = deepcopy(manager.project.files["nested/chapter.txt"].get_item(10).to_dict())
    monkeypatch.setattr(manager, "save_to_file", lambda: (_ for _ in ()).throw(PermissionError("secret path")))
    with pytest.raises(ApplicationError, match="item_save_failed"):
        ItemService(manager).patch_item("nested/chapter.txt", 10, {"translated_text": "edited"})
    assert manager.project.files["nested/chapter.txt"].get_item(10).to_dict() == original


@pytest.mark.parametrize("operation", ["edit", "check"])
def test_mutations_refuse_active_task(manager, monkeypatch, operation):
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    with pytest.raises(ApplicationError, match="operation_busy"):
        if operation == "edit":
            ItemService(manager).patch_item("nested/chapter.txt", 10, {"translated_text": "edited"})
        else:
            CheckService(manager).run_check("rule", {})
    assert ItemService(manager).list_items()["total"] == 4


def test_rule_checker_reuses_real_logic_and_options(manager):
    options = {rule: False for rule in CheckService.RULES}
    options.update(number=True, untranslated=True)
    result = CheckService(manager).run_check("rule", {"rules": options})
    assert not result["passed"]
    assert {issue["index"] for issue in result["issues"]} == {10, 40}
    assert result["issues"][0]["position"] == 0
    assert ConfigService().get_config()["rule_check_placeholder"] is False
    assert CheckService(manager).run_check("rule", {})["issues"] == result["issues"]


def test_terminology_checker_uses_existing_project_analysis(manager):
    manager.set_analysis_data({"terms": [{"source": "Hello", "recommended_translation": "问候"}]})
    result = CheckService(manager).run_check("terminology", {"case_sensitive": True, "whole_word": True})
    # Actual cache analysis structure is read through the original manager.
    assert result["kind"] == "terminology"
    assert [issue["index"] for issue in result["issues"]] == [10]
    assert ConfigService().get_config()["prompt_dictionary_match_case_sensitive"] is True


def test_language_checker_uses_fixed_local_detector_and_preserves_flags(manager, monkeypatch):
    ConfigService().patch_config({"target_language": "chinese_simplified"})
    monkeypatch.setattr(LanguageChecker, "_run_detection", lambda self, items: [[("en", 0.99)] for _ in items])
    result = CheckService(manager).run_check("language", {"mode": "judge", "chunk_size": 1, "threshold": 0.75, "exclude_non_translate": False})
    assert not result["passed"]
    assert result["issues"]
    assert ItemService(manager).list_items(flagged=True)["total"] >= 2
    report = CheckService(manager).run_check("language", {"mode": "report"})
    assert report["issues"] == []
    assert report["reports"]
    assert "en:" in report["reports"][0]["stats"]


def test_checker_errors_keep_legacy_minimum_translation_rule(manager):
    manager.project.stats_data.line = 1
    manager.save_to_file()
    with pytest.raises(ApplicationError, match="check_no_translation"):
        CheckService(manager).run_check("language", {})
