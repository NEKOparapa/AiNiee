import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from ModuleFolders.Application.ConfigService import ConfigService
from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.ProjectService import ProjectService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Config.FilePathConfig import config_path
from ModuleFolders.Domain.FileReader.FileReader import FileReader
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject, CacheProjectStatistics


def make_project(project_id="fixture-project", path="fixture-input"):
    return CacheProject(
        project_id=project_id, project_name="Fixture project", project_type="Txt",
        project_create_time="2026-01-01T00:00:00", input_path=str(path),
        stats_data=CacheProjectStatistics(total_line=4, line=2, token=55),
        files={
            "chapter/a.txt": CacheFile(
                storage_path="chapter/a.txt", file_project_type="Txt", encoding="utf-8",
                language_stats=[("en", 2, 0.95)],
                items=[CacheItem(text_index=1, source_text="First line."), CacheItem(
                    text_index=2, source_text="Second line.", translated_text="第二行。",
                    translation_status=TranslationStatus.TRANSLATED,
                )],
            ),
            "b.txt": CacheFile(storage_path="b.txt", file_project_type="Txt", items=[
                CacheItem(text_index=3, source_text="Third line.", translation_status=TranslationStatus.EXCLUDED),
                CacheItem(text_index=4, source_text="Fourth line.", translated_text="第四行。",
                          translation_status=TranslationStatus.POLISHED),
            ]),
        },
    )


@pytest.fixture
def manager():
    manager = CacheManager()
    yield manager
    manager._cleanup_event_subscriptions()


def service_with_project(manager, project=None):
    reader = Mock()
    reader.get_support_project_types.return_value = ["AutoType", "Txt"]
    reader.read_files.return_value = project or make_project()
    return ProjectService(manager, reader)


def test_open_uses_configured_reader_and_preserves_config(manager, tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    ConfigService().patch_config({"translation_project": "Txt", "label_input_exclude_rule": "*.bak", "custom": 42})
    service = service_with_project(manager, make_project(path=source))
    result = service.open_project(str(source))
    service.file_reader.read_files.assert_called_once_with("Txt", str(source), "*.bak")
    assert result["project_id"] == "fixture-project"
    assert result["item_count"] == 4
    assert Path(CacheManager.get_default_cache_path(project_id=result["project_id"])).is_file()
    saved = json.loads(config_path().read_text(encoding="utf-8"))
    assert saved["label_input_path"] == str(source)
    assert saved["custom"] == 42
    assert service.get_current()["project"] == result


@pytest.mark.parametrize("project_type", ["Txt", "AutoType"])
def test_open_real_text_reader_and_file_tree(manager, tmp_path, project_type):
    source = tmp_path / "source"
    (source / "nested").mkdir(parents=True)
    (source / "nested" / "sample.txt").write_text("Hello, world!\nThis is a project loading test.\n", encoding="utf-8")
    ConfigService().patch_config({"translation_project": project_type, "source_language": "english"})
    service = ProjectService(manager, FileReader())
    summary = service.open_project(str(source))
    assert summary["file_count"] == 1
    assert summary["item_count"] == 2
    files = service.get_files()
    assert Path(files[0]["path"]).as_posix() == "nested/sample.txt"
    assert files[0]["encoding"] == "utf-8"
    assert service.get_stats()["untranslated"] == 2


def test_stats_are_based_on_actual_items_not_stale_task_progress(manager):
    manager.load_from_project(make_project())
    service = service_with_project(manager)
    assert service.get_stats() == {
        "total": 4, "untranslated": 1, "translated": 1, "polished": 1,
        "excluded": 1, "questionable": 0, "other": 0,
        "progress": manager.project.stats_data.to_dict(),
    }
    assert service.get_files()[1]["language_stats"] == [{"language": "en", "count": 2, "confidence": 0.95}]


@pytest.mark.parametrize("failure", ["read", "empty", "save", "config"])
def test_failed_open_keeps_previous_project_and_config(manager, tmp_path, monkeypatch, failure):
    source = tmp_path / "input"
    source.mkdir()
    previous = make_project("previous")
    manager.load_from_project(previous)
    ConfigService().patch_config({"translation_project": "Txt", "label_input_path": str(tmp_path / "old")})
    before = config_path().read_bytes()
    service = service_with_project(manager)
    if failure == "read":
        service.file_reader.read_files.side_effect = ValueError("fixture failure")
    elif failure == "empty":
        service.file_reader.read_files.return_value = CacheProject()
    elif failure == "save":
        monkeypatch.setattr(CacheManager, "_write_project_cache_files", Mock(side_effect=OSError("fixture failure")))
    else:
        monkeypatch.setattr(service, "update_config", Mock(side_effect=OSError("fixture failure")))
    with pytest.raises(ApplicationError):
        service.open_project(str(source))
    assert manager.project is previous
    assert config_path().read_bytes() == before


@pytest.mark.parametrize("status", [Base.STATUS.TASKING, Base.STATUS.STOPING, Base.STATUS.API_TEST, Base.STATUS.ANALYSIS_TASK])
def test_running_task_blocks_project_switch(manager, tmp_path, monkeypatch, status):
    monkeypatch.setattr(Base, "work_status", status)
    service = service_with_project(manager)
    with pytest.raises(ApplicationError, match="operation_busy"):
        service.open_project(str(tmp_path))
    service.file_reader.read_files.assert_not_called()


def test_concurrent_opens_do_not_replace_in_flight_project(manager, tmp_path):
    entered = threading.Event()
    release = threading.Event()
    service = service_with_project(manager)

    def read(*args):
        entered.set()
        assert release.wait(5)
        return make_project()

    service.file_reader.read_files.side_effect = read
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.open_project, str(tmp_path))
        try:
            assert entered.wait(5)
            with pytest.raises(ApplicationError, match="operation_busy"):
                service.open_project(str(tmp_path))
        finally:
            release.set()
        assert first.result(timeout=5)["project_id"] == "fixture-project"


def test_invalid_missing_and_empty_paths_are_reported(manager, tmp_path):
    service = service_with_project(manager)
    for path, code in [(" ", "project_path_invalid"), ("bad\x00path", "project_path_invalid"), (str(tmp_path / "missing"), "project_path_not_found")]:
        with pytest.raises(ApplicationError, match=code):
            service.open_project(path)


@pytest.mark.parametrize("project_id", ["..", "../outside", "a/b", "a\\b", "C:outside"])
def test_cache_id_cannot_escape_cache_root(manager, tmp_path, project_id):
    service = service_with_project(manager, make_project(project_id))
    with pytest.raises(ApplicationError, match="project_cache_invalid"):
        service.open_project(str(tmp_path))
    assert manager.project is None


def test_directory_browser_lists_children_and_accepts_file_parent(manager, tmp_path):
    (tmp_path / "z-folder").mkdir()
    (tmp_path / "a.txt").write_text("example", encoding="utf-8")
    service = service_with_project(manager)
    listing = service.list_directory(str(tmp_path / "a.txt"))
    assert listing["path"] == str(tmp_path)
    assert listing["parent"] == str(tmp_path.parent)
    assert listing["roots"]
    assert listing["entries"] == [
        {"name": "z-folder", "path": str(tmp_path / "z-folder"), "is_directory": True},
        {"name": "a.txt", "path": str(tmp_path / "a.txt"), "is_directory": False},
    ]


def test_empty_project_returns_explicit_state(manager):
    service = service_with_project(manager)
    assert service.get_current()["project"] is None
    for operation in (service.get_files, service.get_stats):
        with pytest.raises(ApplicationError, match="project_not_open"):
            operation()


def test_open_notifies_after_current_project_is_published(manager, tmp_path):
    received = []
    service = service_with_project(manager)
    events = EventManager.get_singleton()

    def changed(event, data):
        received.append((data, service.get_current()["project"]["project_id"]))

    events.subscribe(Base.EVENT.PROJECT_CHANGED, changed)
    try:
        service.open_project(str(tmp_path))
    finally:
        events.unsubscribe(Base.EVENT.PROJECT_CHANGED, changed)
    assert received == [({"project_id": "fixture-project"}, "fixture-project")]


def test_restore_cache_preserves_translation_stats_and_extra(manager, tmp_path):
    cached = make_project("saved", tmp_path / "original-input")
    cached.extra["extension"] = {"keep": "original"}
    CacheManager._write_project_cache_files(cached)
    path = CacheManager.get_default_cache_path(project_id="saved")
    service = service_with_project(manager)
    summary = service.open_project(path)
    service.file_reader.read_files.assert_not_called()
    assert summary["project_id"] == "saved"
    assert manager.project.files["chapter/a.txt"].items[1].translated_text == "第二行。"
    assert manager.project.stats_data.line == 2
    assert manager.project.extra == {"extension": {"keep": "original"}}
    assert ConfigService().get_config()["label_input_path"] == str(tmp_path / "original-input")


def test_restore_legacy_list_cache_uses_existing_converter(manager, tmp_path):
    source = tmp_path / "AinieeCacheData-legacy.json"
    source.write_text(json.dumps([
        {"project_id": "legacy-id", "project_name": "Old project", "project_type": "Txt",
         "project_create_time": "2020-01-01", "input_path": str(tmp_path / "legacy-input"),
         "data": {"total_line": 2, "line": 1, "token": 64}},
        {"storage_path": "old.txt", "text_index": 1, "source_text": "Old source",
         "translated_text": "旧译文", "translation_status": 1, "plugin_value": "preserve"},
        {"storage_path": "old.txt", "text_index": 2, "source_text": "Next source", "translation_status": 0},
    ], ensure_ascii=False), encoding="utf-8")
    service = service_with_project(manager)
    service.open_project(str(source))
    assert manager.project.project_id == "legacy-id"
    assert manager.project.files["old.txt"].items[0].translated_text == "旧译文"
    assert manager.project.files["old.txt"].items[0].extra["plugin_value"] == "preserve"
    assert manager.project.stats_data.line == 1
    assert manager.project.stats_data.token == 64
    assert service.get_stats()["untranslated"] == 1


def test_open_current_cache_never_overwrites_unsaved_in_memory_edits(manager):
    manager.load_from_project(make_project())
    manager.save_to_file()
    project = manager.project
    project.files["chapter/a.txt"].items[1].translated_text = "最新的人工校对"
    service = service_with_project(manager)
    service.open_project(CacheManager.get_default_cache_path(project_id=project.project_id))
    assert manager.project is project
    assert manager.project.files["chapter/a.txt"].items[1].translated_text == "最新的人工校对"


def test_history_keeps_more_than_three_and_never_deletes_damaged_caches(manager):
    for index in range(5):
        cached = make_project(f"saved-{index}")
        cached.project_create_time = f"2026-01-0{index + 1}T00:00:00"
        CacheManager._write_project_cache_files(cached)
    root = Path(CacheManager.get_project_cache_root())
    broken = root / "broken"
    broken.mkdir()
    (broken / CacheManager.CACHE_FILENAME).write_bytes(b"broken-cache")
    (broken / CacheManager.STATS_FILENAME).write_bytes(b"broken-statistics")
    incomplete = root / "incomplete"
    incomplete.mkdir()
    (incomplete / CacheManager.STATS_FILENAME).write_bytes(b"{}")
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    history = service_with_project(manager).get_history()
    assert len(history) == 6
    assert {entry["project_id"] for entry in history} >= {f"saved-{index}" for index in range(5)}
    assert any(entry["project_id"] == "broken" for entry in history)
    assert {path: path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


def test_switching_projects_saves_previous_progress_before_restore(manager):
    previous = make_project("previous")
    manager.load_from_project(previous)
    previous.files["chapter/a.txt"].items[1].translated_text = "保留人工修改"
    CacheManager._write_project_cache_files(make_project("next"))
    service = service_with_project(manager)
    service.open_project(CacheManager.get_default_cache_path(project_id="next"))
    reloaded = CacheManager.read_from_file(CacheManager.get_default_cache_path(project_id="previous"))
    assert reloaded.files["chapter/a.txt"].items[1].translated_text == "保留人工修改"
    assert manager.project.project_id == "next"


def test_history_delete_rejects_current_and_notifies_for_other_cache(manager):
    manager.load_from_project(make_project("current"))
    manager.save_to_file()
    CacheManager._write_project_cache_files(make_project("other"))
    service = service_with_project(manager)
    with pytest.raises(ApplicationError, match="project_history_current"):
        service.delete_history("current")
    events = EventManager.get_singleton()
    received = []

    def changed(event, data):
        received.append(data)

    events.subscribe(Base.EVENT.PROJECT_HISTORY_CHANGED, changed)
    try:
        assert service.delete_history("other") == {"deleted": True}
    finally:
        events.unsubscribe(Base.EVENT.PROJECT_HISTORY_CHANGED, changed)
    assert received == [{}]
    assert not Path(CacheManager.get_project_cache_dir("other")).exists()
    assert Path(CacheManager.get_project_cache_dir("current")).is_dir()
    with pytest.raises(ApplicationError, match="project_history_not_found"):
        service.delete_history("other")


@pytest.mark.skipif(os.name != "nt", reason="Windows paths are case insensitive")
def test_history_delete_cannot_bypass_current_guard_with_case_alias(manager):
    manager.load_from_project(make_project("CurrentProject"))
    manager.save_to_file()
    directory = Path(CacheManager.get_project_cache_dir("CurrentProject"))
    before = (directory / CacheManager.CACHE_FILENAME).read_bytes()
    with pytest.raises(ApplicationError, match="project_history_current"):
        service_with_project(manager).delete_history("CURRENTPROJECT")
    assert (directory / CacheManager.CACHE_FILENAME).read_bytes() == before


def external_backup(tmp_path, project_id="collision"):
    older = make_project(project_id, tmp_path / "old-backup-input")
    older.files["chapter/a.txt"].items[1].translated_text = "旧备份译文"
    older.stats_data.line = 1
    source = tmp_path / "AinieeCacheData-external.json"
    source.write_text(json.dumps(older.to_dict(), ensure_ascii=False), encoding="utf-8")
    return source


def cache_bytes(project_id):
    directory = Path(CacheManager.get_project_cache_dir(project_id))
    return {
        filename: (directory / filename).read_bytes() if (directory / filename).exists() else None
        for filename in (CacheManager.CACHE_FILENAME, CacheManager.STATS_FILENAME)
    }


@pytest.mark.parametrize("failure", ["config", "config_after_save", "install"])
def test_colliding_backup_rolls_back_history_and_config_on_install_failure(manager, tmp_path, monkeypatch, failure):
    current = make_project("current")
    manager.load_from_project(current)
    newer = make_project("collision")
    newer.files["chapter/a.txt"].items[1].translated_text = "最新译文不能丢"
    newer.stats_data.line = 2
    CacheManager._write_project_cache_files(newer)
    ConfigService().patch_config({"label_input_path": str(tmp_path / "current-input"), "keep": "original"})
    source = external_backup(tmp_path)
    original_history = cache_bytes("collision")
    original_config = config_path().read_bytes()
    original_source = source.read_bytes()
    service = service_with_project(manager)
    update = service.update_config

    def fail_config(updater):
        if failure == "config_after_save":
            update(updater)
        raise OSError("fixture config save failure")

    def fail_install(candidate):
        manager.project = candidate
        raise OSError("fixture install failure")

    if failure == "install":
        monkeypatch.setattr(manager, "load_from_project", fail_install)
    else:
        monkeypatch.setattr(service, "update_config", fail_config)
    with pytest.raises(ApplicationError, match="project_save_failed"):
        service.open_project(str(source))
    assert manager.project is current
    assert cache_bytes("collision") == original_history
    assert config_path().read_bytes() == original_config
    assert source.read_bytes() == original_source
    assert not list(Path(CacheManager.get_project_cache_root()).rglob("*.backup"))


@pytest.mark.parametrize("existing", ["both", "cache_only", "neither"])
def test_candidate_second_file_failure_restores_existing_bytes_and_absence(manager, tmp_path, monkeypatch, existing):
    current = make_project("current")
    manager.load_from_project(current)
    if existing != "neither":
        CacheManager._write_project_cache_files(make_project("collision"))
    directory = Path(CacheManager.get_project_cache_dir("collision"))
    stats_path = directory / CacheManager.STATS_FILENAME
    if existing == "cache_only":
        stats_path.unlink()
    source = external_backup(tmp_path)
    ConfigService().patch_config({"label_input_path": str(tmp_path / "original-input")})
    original_history = cache_bytes("collision")
    original_config = config_path().read_bytes()
    replace = os.replace

    def fail_second_file(source_path, target_path):
        if Path(target_path) == stats_path and str(source_path).endswith(".tmp"):
            raise OSError("fixture statistics write failure")
        return replace(source_path, target_path)

    monkeypatch.setattr(os, "replace", fail_second_file)
    with pytest.raises(ApplicationError, match="project_save_failed"):
        service_with_project(manager).open_project(str(source))
    assert manager.project is current
    assert cache_bytes("collision") == original_history
    assert config_path().read_bytes() == original_config
    assert not list(Path(CacheManager.get_project_cache_root()).rglob("*.backup"))
