from concurrent.futures import ThreadPoolExecutor

import pytest

from ModuleFolders.Application.TaskService import STATUS_NAMES, TaskService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject, CacheProjectStatistics


@pytest.fixture
def manager():
    cache = CacheManager()
    yield cache
    cache._cleanup_event_subscriptions()


@pytest.mark.parametrize("status,name", [*STATUS_NAMES.items(), (-1, "unknown")])
def test_current_task_maps_every_legacy_state_without_mutating_it(manager, monkeypatch, status, name):
    monkeypatch.setattr(Base, "work_status", status)
    assert TaskService(manager).get_current() == {
        "status": name, "project_id": None, "project_name": None, "progress": {},
    }
    assert Base.work_status == status


def test_current_task_reads_existing_progress_and_returns_detached_data(manager, monkeypatch):
    monkeypatch.setattr(Base, "work_status", Base.STATUS.TASKING)
    stats = CacheProjectStatistics(total_line=10, line=3, token=120)
    manager.project = CacheProject(project_id="project-id", project_name="Existing project", stats_data=stats)
    result = TaskService(manager).get_current()
    assert result["status"] == "running"
    assert result["project_id"] == "project-id"
    assert result["project_name"] == "Existing project"
    assert result["progress"]["line"] == 3
    assert result["progress"]["token"] == 120
    result["progress"]["line"] = 99
    assert manager.project.stats_data.line == 3


def test_statistics_snapshot_uses_existing_atomic_scope(manager):
    stats = CacheProjectStatistics()
    manager.project = CacheProject(stats_data=stats)
    service = TaskService(manager)

    def update():
        for count in range(500):
            with stats.atomic_scope():
                stats.line = count
                stats.token = count * 10

    with ThreadPoolExecutor(max_workers=1) as executor:
        updating = executor.submit(update)
        for _ in range(500):
            snapshot = service.get_current()["progress"]
            assert snapshot["token"] == snapshot["line"] * 10
        updating.result(timeout=3)
