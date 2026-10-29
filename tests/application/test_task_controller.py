from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Application.TaskService import TaskService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject, CacheProjectStatistics


@pytest.fixture
def controller(tmp_path, monkeypatch):
    ConfigMixin().save_config({
        "platforms": {"mock": {"api_key": "test-secret", "api_url": "https://llm.invalid", "model": "fixed"}},
        "api_settings": {"active": "mock"}, "label_input_path": str(tmp_path),
    })
    cache = CacheManager()
    cache.SAVE_INTERVAL = 0.02
    cache.load_from_project(CacheProject(project_id="test-project", project_name="Test", files={
        "test.txt": CacheFile(storage_path="test.txt", items=[CacheItem(source_text="Hello")]),
    }))
    executor = SimpleNamespace(translation_start_target=Mock(), polish_start_target=Mock(), analysis_start_target=Mock())
    service = TaskService(cache, executor)
    monkeypatch.setattr(service, "_cancel_requests", Mock())
    yield service
    assert service.close(5), "Task worker leaked"
    cache._cleanup_event_subscriptions()


def emit(event, data=None):
    EventManager.get_singleton().emit(event, data or {})


def test_worker_remains_exclusive_until_legacy_finalization_finishes(controller):
    in_cleanup, release = Event(), Event()

    def target(continuing):
        assert not continuing
        Base.work_status = Base.STATUS.IDLE  # The old target does this too early.
        emit(Base.EVENT.TASK_STOP_DONE)
        in_cleanup.set()
        assert release.wait(5)
        emit(Base.EVENT.TASK_COMPLETED)

    controller.task_executor.translation_start_target.side_effect = target
    controller.translate()
    try:
        assert in_cleanup.wait(5)
        assert controller.get_current()["status"] == "running"
        with pytest.raises(ApplicationError, match="operation_busy"):
            with exclusive_operation():
                pytest.fail("Another mutation entered during task cleanup")
        with pytest.raises(ApplicationError, match="operation_busy"):
            controller.translate()
    finally:
        release.set()
    assert controller.wait(5)
    assert controller.get_current()["status"] == "completed"
    with exclusive_operation():
        pass


def test_stop_before_legacy_initial_update_is_not_lost(controller):
    entered, release = Event(), Event()

    def target(continuing):
        entered.set()
        assert release.wait(5)
        Base.work_status = Base.STATUS.TASKING
        emit(Base.EVENT.TASK_UPDATE)
        assert Base.work_status == Base.STATUS.STOPING

    controller.task_executor.translation_start_target.side_effect = target
    controller.translate()
    try:
        assert entered.wait(5)
        assert controller.stop()["status"] == "stopping"
    finally:
        release.set()
    assert controller.wait(5)
    assert controller.get_current()["status"] == "stopped"
    assert Base.work_status == Base.STATUS.IDLE
    controller._cancel_requests.assert_called()


def test_exception_releases_state_and_can_start_again(controller):
    controller.task_executor.translation_start_target.side_effect = RuntimeError("provider test-secret")
    controller.translate()
    assert controller.wait(5)
    result = controller.get_current()
    assert result["status"] == "failed"
    assert result["last_error"] == "task_execution_failed"
    controller.task_executor.translation_start_target.side_effect = lambda continuing: emit(Base.EVENT.TASK_COMPLETED)
    controller.translate()
    assert controller.wait(5)
    assert controller.get_current()["status"] == "completed"


def test_analysis_snapshot_and_error_event(controller):
    update = {"status": "running", "phase": "stage1", "phase_label": "阶段一", "current": 1, "total": 2,
              "percent": 35, "message": "progress", "detail": "1/2"}

    def target():
        emit(Base.EVENT.ANALYSIS_TASK_UPDATE, update)
        emit(Base.EVENT.ANALYSIS_TASK_DONE, {"status": "error", "message": "provider test-secret"})

    controller.task_executor.analysis_start_target.side_effect = target
    controller.analysis()
    assert controller.wait(5)
    snapshot = controller.get_current()
    assert snapshot["status"] == "failed"
    assert snapshot["analysis_progress"] == update
    snapshot["analysis_progress"]["message"] = "changed"
    assert controller.get_current()["analysis_progress"]["message"] == "progress"
    assert "test-secret" not in str(snapshot)


def test_resume_polishing_uses_existing_statistics(controller):
    project = controller.cache_manager.project
    next(project.items_iter()).translation_status = TranslationStatus.TRANSLATED
    project.stats_data = CacheProjectStatistics(line=1, total_line=2)
    controller.task_executor.polish_start_target.side_effect = lambda continuing: emit(Base.EVENT.TASK_COMPLETED)
    controller.polish(True)
    assert controller.wait(5)
    controller.task_executor.polish_start_target.assert_called_once_with(True)
    assert controller.get_current()["mode"] == "polish"


def test_start_validates_project_platform_pending_and_resume(controller):
    with pytest.raises(ApplicationError, match="task_cannot_continue"):
        controller.translate(True)
    with pytest.raises(ApplicationError, match="task_no_pending_items"):
        controller.polish()
    ConfigMixin().save_config({"platforms": {}, "api_settings": {}})
    with pytest.raises(ApplicationError, match="task_platform_required"):
        controller.translate()
    controller.cache_manager.project = None
    with pytest.raises(ApplicationError, match="project_not_open"):
        controller.translate()


def test_autosave_is_joined_on_close(controller, monkeypatch):
    saved = Event()
    real_save = controller.cache_manager.save_to_file

    def save():
        real_save()
        saved.set()

    def target(continuing):
        saved.clear()
        controller.cache_manager.require_save_to_file()
        assert saved.wait(5)
        emit(Base.EVENT.TASK_COMPLETED)

    monkeypatch.setattr(controller.cache_manager, "save_to_file", save)
    controller.task_executor.translation_start_target.side_effect = target
    controller.translate()
    assert controller.wait(5)
    assert controller.get_current()["status"] == "completed"
    assert controller.close()
    with pytest.raises(ApplicationError, match="task_service_unavailable"):
        controller.translate()


def test_final_cache_save_failure_reports_failed_and_releases_guard(controller, monkeypatch):
    def target(continuing):
        monkeypatch.setattr(controller.cache_manager, "save_to_file", Mock(side_effect=OSError("disk full")))
        emit(Base.EVENT.TASK_COMPLETED)

    controller.task_executor.translation_start_target.side_effect = target
    controller.translate()
    assert controller.wait(5)
    assert controller.get_current()["last_error"] == "cache_save_failed"
    assert controller.get_current()["status"] == "failed"
    with exclusive_operation():
        pass


def test_worker_secret_redaction_reaches_nested_threads_and_expires(controller):
    from ModuleFolders.Log.LogSystem import redact

    observed = []
    ConfigMixin().save_config({
        "platforms": {"mock": {
            "api_key": "test-secret, second-secret", "extra_headers": {"Authorization": "Bearer header-secret"},
        }},
    })

    def target(continuing):
        nested = Thread(target=lambda: observed.append(redact("raw test-secret second-secret header-secret response")))
        nested.start()
        nested.join(3)
        assert not nested.is_alive()
        emit(Base.EVENT.TASK_COMPLETED)

    controller.task_executor.translation_start_target.side_effect = target
    controller.translate()
    assert controller.wait(5)
    assert "test-secret" not in observed[0]
    assert "second-secret" not in observed[0]
    assert "header-secret" not in observed[0]
    assert redact("raw test-secret response") == "raw test-secret response"


def test_timed_close_keeps_guard_until_final_save_then_cleans_subscriptions(controller):
    entered, release = Event(), Event()

    def target(continuing):
        entered.set()
        assert release.wait(5)
        emit(Base.EVENT.TASK_COMPLETED)

    controller.task_executor.translation_start_target.side_effect = target
    controller.translate()
    try:
        assert entered.wait(5)
        assert controller.close(0.01) is False
        with pytest.raises(ApplicationError, match="operation_busy"):
            with exclusive_operation():
                pytest.fail("Closing a live task released the application guard")
    finally:
        release.set()
    assert controller.wait(5)
    for event in controller._events:
        assert controller._on_event not in controller._manager.event_callbacks.get(event, [])
    with exclusive_operation():
        pass
