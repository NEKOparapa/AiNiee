from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject
from Server.app import create_app


TOKEN = "fixed-task-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def task_client(tmp_path):
    ConfigMixin().save_config({
        "label_input_path": str(tmp_path), "platforms": {"mock": {"api_key": "mock-key"}},
        "api_settings": {"active": "mock"},
    })
    cache = CacheManager()
    cache.load_from_project(CacheProject(project_id="test", project_name="Test", files={
        "sample.txt": CacheFile(storage_path="sample.txt", items=[CacheItem(source_text="Hello")]),
    }))
    executor = SimpleNamespace(
        translation_start_target=Mock(), polish_start_target=Mock(), analysis_start_target=Mock(),
        _resolve_output_source_language=lambda value: "en", _resolve_output_target_language=lambda value: "zh-Hans",
    )

    def write(project, output, source, config):
        directory = Path(output)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "sample_translated.txt").write_text("你好", encoding="utf-8")

    runtime = SimpleNamespace(
        cache_manager=cache, task_executor=executor,
        file_writer=SimpleNamespace(output_translated_content=write), close=cache._cleanup_event_subscriptions,
    )
    app = create_app(TOKEN, runtime_factory=lambda: runtime)
    with TestClient(app) as client:
        app.state.task_service._cancel_requests = Mock()
        yield client, app.state.task_service, executor


def test_task_export_commands_require_token_and_validate_request(task_client):
    client, service, executor = task_client
    for path in ("tasks/translate", "tasks/polish", "tasks/analysis", "tasks/stop", "export", "cache/save"):
        assert client.post("/api/v1/" + path, json={}).status_code == 401
    for body in ({"unexpected": 1}, {"continue": "invalid"}):
        assert client.post("/api/v1/tasks/translate", json=body, headers=AUTH).status_code == 422
    assert client.post("/api/v1/export", json={"output_path": ""}, headers=AUTH).status_code == 422
    executor.translation_start_target.assert_not_called()


def test_http_start_current_stop_and_busy_mutations(task_client):
    client, service, executor = task_client
    entered, release = Event(), Event()

    def target(continuing):
        entered.set()
        assert release.wait(5)

    executor.translation_start_target.side_effect = target
    response = client.post("/api/v1/tasks/translate", json={"continue": False}, headers=AUTH)
    try:
        assert response.status_code == 200
        assert response.json()["mode"] == "translate"
        assert entered.wait(5)
        assert client.get("/api/v1/tasks/current", headers=AUTH).json()["status"] == "running"
        assert client.post("/api/v1/tasks/analysis", headers=AUTH).status_code == 409
        assert client.post("/api/v1/cache/save", headers=AUTH).status_code == 409
        assert client.post("/api/v1/export", json={}, headers=AUTH).status_code == 409
        assert client.post("/api/v1/tasks/stop", headers=AUTH).json()["status"] == "stopping"
    finally:
        release.set()
    assert service.wait(5)
    assert client.get("/api/v1/tasks/current", headers=AUTH).json()["status"] == "stopped"
    assert client.post("/api/v1/cache/save", headers=AUTH).json() == {"saved": True}


def test_http_analysis_and_export_response_contract(task_client, tmp_path):
    client, service, executor = task_client

    def target():
        manager = EventManager.get_singleton()
        manager.emit(Base.EVENT.ANALYSIS_TASK_UPDATE, {"phase": "finalize", "percent": 100})
        manager.emit(Base.EVENT.ANALYSIS_TASK_DONE, {"status": "success"})

    executor.analysis_start_target.side_effect = target
    assert client.post("/api/v1/tasks/analysis", headers=AUTH).status_code == 200
    assert service.wait(5)
    snapshot = client.get("/api/v1/tasks/current", headers=AUTH).json()
    assert snapshot["mode"] == "analysis"
    assert snapshot["status"] == "completed"
    assert snapshot["analysis_progress"]["percent"] == 100
    exported = client.post("/api/v1/export", json={"output_path": str(tmp_path / "out")}, headers=AUTH)
    assert exported.status_code == 200
    assert exported.json() == {"output_path": str(tmp_path / "out"), "files": ["sample_translated.txt"]}


def test_shutdown_waits_for_worker_final_save_before_closing_runtime(tmp_path, monkeypatch):
    ConfigMixin().save_config({"platforms": {"mock": {"api_key": "test-key"}}, "api_settings": {"active": "mock"}})
    entered, release, closing, persisted, runtime_closed = (Event() for _ in range(5))
    cache = CacheManager()
    cache.load_from_project(CacheProject(project_id="shutdown", project_name="Shutdown", input_path=str(tmp_path), files={
        "sample.txt": CacheFile(storage_path="sample.txt", items=[CacheItem(source_text="Hello")]),
    }))
    real_save = cache.save_to_file

    def save():
        real_save()
        if next(cache.project.items_iter()).translated_text == "saved before shutdown":
            persisted.set()

    monkeypatch.setattr(cache, "save_to_file", save)

    def target(continuing):
        entered.set()
        assert release.wait(5)
        next(cache.project.items_iter()).translated_text = "saved before shutdown"
        EventManager.get_singleton().emit(Base.EVENT.TASK_COMPLETED, {})

    def close_runtime():
        assert persisted.is_set(), "Runtime closed before final task persistence"
        cache._cleanup_event_subscriptions()
        runtime_closed.set()

    runtime = SimpleNamespace(cache_manager=cache, task_executor=SimpleNamespace(translation_start_target=target), close=close_runtime)
    app = create_app(TOKEN, runtime_factory=lambda: runtime)
    errors, observed_timeouts = [], []

    def app_thread():
        try:
            with TestClient(app) as client:
                service = app.state.task_service
                service._cancel_requests = Mock()
                real_close = service.close

                def checked_close(timeout=10):
                    observed_timeouts.append(timeout)
                    closing.set()
                    # Keep a regression to finite shutdown bounded in this test.
                    return real_close(None if timeout is None else 0.01)

                service.close = checked_close
                assert client.post("/api/v1/tasks/translate", json={}, headers=AUTH).status_code == 200
                assert entered.wait(5)
        except BaseException as error:
            errors.append(error)

    worker = Thread(target=app_thread)
    worker.start()
    try:
        assert closing.wait(5)
        assert observed_timeouts == [None]
        assert not runtime_closed.wait(0.05)
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert not errors, errors
    assert runtime_closed.is_set()
    for event in app.state.task_service._events:
        assert app.state.task_service._on_event not in EventManager.get_singleton().event_callbacks.get(event, [])
