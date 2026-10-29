import base64
import json

import pytest

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.PromptService import PromptService
from ModuleFolders.Application.TableService import TableService
from ModuleFolders.Config.Config import ConfigMixin


def test_legacy_tables_are_available_with_matching_metadata():
    ConfigMixin().save_config({"prompt_dictionary_data": [{"src": "Alice", "dst": "爱丽丝", "origin": {"chapter": 2}}], "prompt_dictionary_switch": True, "prompt_dictionary_match_case_sensitive": True})
    result = TableService().get("glossary")
    table = result["tables"][0]
    assert result["active_table_id"] == table["id"]
    assert table["rows"][0]["origin"] == {"chapter": 2}
    assert table["enabled"] is True
    assert table["match_options"]["case_sensitive"] is True


def test_existing_multitable_and_extra_fields_survive_config_normalization():
    ConfigMixin().save_config({"prompt_dictionary_tables": [{"id": "existing", "name": "Imported", "enabled": False, "rows": [{"src": "猫", "dst": "cat", "provenance": "chapter1"}], "future_table_data": {"version": 2}}], "prompt_dictionary_active_table_id": "existing", "unrelated": {"keep": True}})
    service = TableService()
    assert service.get("glossary")["tables"][0]["future_table_data"] == {"version": 2}
    assert service.load_config()["unrelated"] == {"keep": True}


def test_libraries_read_all_old_storages_and_integer_presets():
    config = {}
    for kind, (selection, custom) in PromptService.LIBRARIES.items():
        config[selection] = {"last_selected_id": kind, "prompt_content": "selected " + kind, "future": "keep"}
        config[custom] = [{"id": kind, "name": kind, "type": "user", "content": "stored " + kind, "future": {"value": 1}}]
    ConfigMixin().save_config(config)
    service = PromptService()
    for kind in PromptService.LIBRARIES:
        library = service.get_library(kind)
        assert isinstance(library["presets"][0]["id"], int)
        assert library["custom"][0]["future"] == {"value": 1}
        assert service.get(kind)["content"] == "selected " + kind


def test_text_and_examples_read_legacy_configuration():
    ConfigMixin().save_config({"world_building_switch": True, "world_building_content": "Custom world", "translation_example_data": [{"src": "one", "dst": "一", "extra": "retained"}]})
    service = PromptService()
    assert service.get("world")["content"] == "Custom world"
    assert service.get("world")["enabled"] is True
    assert service.get("examples")["rows"][0]["extra"] == "retained"
    assert service.get("style")["content"]


def test_unknown_documents_are_not_created():
    for action in (lambda: TableService().get("bad"), lambda: PromptService().get("bad"), lambda: PromptService().get_library("world")):
        with pytest.raises(ApplicationError):
            action()


def test_prompt_edits_preserve_legacy_rows_and_unrelated_configuration():
    ConfigMixin().save_config({"future_settings": {"value": 3}, "translation_example_data": [{"src": "hello", "dst": "你好", "future": {"v": 1}}]})
    service = PromptService()
    document = service.get("examples")
    document["rows"][0]["dst"] = "您好"
    document["enabled"] = True
    assert service.put("examples", document)["rows"][0]["future"] == {"v": 1}
    service.put("world", {"enabled": True, "content": "Changed background"})
    saved = service.load_config()
    assert saved["world_building_content"] == "Changed background"
    assert saved["translation_example_switch"] is True
    assert saved["future_settings"] == {"value": 3}


def test_selecting_a_prompt_preserves_extra_selection_fields_and_original_id_type():
    ConfigMixin().save_config({"translation_prompt_selection": {"future": True, "last_selected_id": 100, "prompt_content": "old"}})
    service = PromptService()
    result = service.put("system", {"selected_id": "200", "content": "must not replace system preset"})
    assert result["selected_id"] == 200
    assert result["content"] == service.get_library("system")["presets"][1]["content"]
    assert service.load_config()["translation_prompt_selection"]["future"] is True


def test_prompt_mutation_is_blocked_during_tasks(monkeypatch):
    from ModuleFolders.Base.Base import Base
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    with pytest.raises(ApplicationError, match="operation_busy"):
        PromptService().put("world", {"enabled": True, "content": "unsafe"})


def test_append_analysis_rows_selects_target_and_deduplicates_without_overwriting():
    ConfigMixin().save_config({"prompt_dictionary_tables": [{"id": "a", "name": "A", "enabled": True, "rows": [{"src": "Alice", "dst": "旧译名", "origin": "manual"}]}, {"id": "b", "name": "B", "enabled": False, "rows": []}], "prompt_dictionary_active_table_id": "b"})
    service = TableService()
    result = service.append_rows("glossary", [{"src": "Alice", "dst": "changed"}, {"src": "Bob", "dst": "鲍勃", "origin": "analysis"}, {"src": "Bob", "dst": "duplicate"}], table_id="a")
    assert result["active_table_id"] == "b"
    assert [(row["src"], row["dst"]) for row in result["tables"][0]["rows"]] == [("Alice", "旧译名"), ("Bob", "鲍勃")]
    assert result["tables"][0]["rows"][0]["origin"] == "manual"
    with pytest.raises(ApplicationError, match="table_not_found"):
        service.append_rows("glossary", [{"src": "new"}], table_id="missing")


def test_append_analysis_characters_writes_the_original_character_storage():
    service = TableService()
    result = service.append_rows("characters", [{"original_name": "Alice", "translated_name": "爱丽丝"}])
    assert result["tables"][0]["rows"][0]["original_name"] == "Alice"
    assert service.load_config()["characterization_data"][0]["translated_name"] == "爱丽丝"


def upload(filename, payload, **options):
    return {"filename": filename, "content_base64": base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode(), **options}


def test_table_full_crud_preserves_fields_and_import_preview_does_not_write():
    service = TableService()
    original = service.get("glossary")
    preview = service.import_file("glossary", upload("legacy.json", {"Alice": "爱丽丝"}, preview=True))
    assert preview["tables"][0]["rows"][0]["src"] == "Alice"
    assert service.get("glossary") == original
    imported = service.import_file("glossary", upload("legacy.json", [{"srt": "Alice", "dst": "爱丽丝", "future": 4}]))
    table = imported["tables"][-1]
    assert table["rows"][0]["future"] == 4
    table["name"] = "Renamed"
    table["enabled"] = False
    table["future_table"] = {"version": 2}
    table["match_options"]["case_sensitive"] = True
    saved = service.put("glossary", imported)
    assert saved["tables"][-1]["future_table"] == {"version": 2}
    assert saved["tables"][-1]["enabled"] is False
    assert saved["tables"][-1]["match_options"]["case_sensitive"] is True
    service.put("glossary", {"tables": [], "active_table_id": None})
    assert service.get("glossary")["tables"] == []


@pytest.mark.parametrize("format", ["json", "xlsx"])
def test_service_bundle_export_import_keeps_table_settings_and_safe_excel_text(format):
    service = TableService()
    service.put("glossary", {"tables": [{"id": "one", "name": "Alpha", "enabled": False, "rows": [{"src": "=SUM(1,2)", "dst": "中文", "regex": True}], "match_options": {"case_sensitive": True}}, {"id": "two", "name": "Beta", "enabled": True, "rows": [{"src": "B", "dst": "二"}]}], "active_table_id": "one"})
    exported = service.export_file("glossary", format=format, bundle=True)
    request = {"filename": exported["filename"], "content_base64": exported["content_base64"], "preview": True}
    preview = service.import_file("glossary", request)
    assert [row["name"] for row in preview["tables"]] == ["Alpha", "Beta"]
    saved = service.import_file("glossary", {**request, "preview": False, "selected_table_ids": ["import-0"]})
    assert len(saved["tables"]) == 3
    imported = saved["tables"][-1]
    assert imported["name"] == "Alpha (2)"
    assert imported["enabled"] is False
    assert imported["match_options"]["case_sensitive"] is True
    assert imported["rows"][0]["src"] == "=SUM(1,2)"


def test_import_merge_keeps_existing_rows_and_rejects_bad_input():
    service = TableService()
    existing = service.append_rows("exclusion", [{"markers": "Alice", "info": "manual"}])
    target = existing["active_table_id"]
    merged = service.import_file("exclusion", upload("data.json", [{"markers": "Alice", "info": "overwrite"}, {"markers": "Bob"}], mode="merge", target_table_id=target))
    assert merged["tables"][0]["rows"][0]["info"] == "manual"
    assert len(merged["tables"][0]["rows"]) == 2
    for request in ({"filename": "bad.csv", "content_base64": ""}, {"filename": "bad.json", "content_base64": "not valid"}, upload("bad.json", {"tables": []})):
        with pytest.raises(ApplicationError, match="table_import_invalid"):
            service.import_file("exclusion", request)


@pytest.mark.parametrize("kind", list(PromptService.LIBRARIES))
def test_custom_library_crud_preserves_metadata_and_restores_selected_preset(kind):
    service = PromptService()
    created = service.upsert(kind, {"name": "Custom", "content": "First", "future": {"keep": True}})
    identifier = created["custom"][0]["id"]
    assert created["selected_id"] == identifier
    service.upsert(kind, {"id": identifier, "name": "Edited", "content": "Second", "select": False})
    assert service.get(kind)["content"] == "Second"
    assert service.get_library(kind)["custom"][0]["future"] == {"keep": True}
    preset = created["presets"][0]["id"]
    with pytest.raises(ApplicationError, match="prompt_readonly"):
        service.upsert(kind, {"id": str(preset), "name": "No", "content": "No"})
    with pytest.raises(ApplicationError, match="prompt_readonly"):
        service.delete(kind, str(preset))
    result = service.delete(kind, identifier)
    assert result["custom"] == []
    assert result["selected_id"] == preset
    assert service.get(kind)["content"] == result["presets"][0]["content"]
