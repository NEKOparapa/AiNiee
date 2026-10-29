"""任务状态只读视图；M2 不新增任务启动、停止或调度能力。"""

from ModuleFolders.Base.Base import Base
from ModuleFolders.Service.Cache.CacheManager import CacheManager


STATUS_NAMES = {
    Base.STATUS.IDLE: "idle",
    Base.STATUS.TASKING: "running",
    Base.STATUS.STOPING: "stopping",
    Base.STATUS.TASKSTOPPED: "stopped",
    Base.STATUS.API_TEST: "api_test",
    Base.STATUS.GLOSS_TASK: "glossary",
    Base.STATUS.ANALYSIS_TASK: "analysis",
    Base.STATUS.TABLE_TASK: "table",
}


class TaskService:
    def __init__(self, cache_manager: CacheManager) -> None:
        self.cache_manager = cache_manager

    def get_current(self) -> dict:
        with self.cache_manager.file_lock:
            project = self.cache_manager.project
        result = {
            "status": STATUS_NAMES.get(Base.work_status, "unknown"),
            "project_id": None,
            "project_name": None,
            "progress": {},
        }
        if project is not None:
            with project.atomic_scope():
                result["project_id"] = project.project_id or None
                result["project_name"] = project.project_name or None
                statistics = project.stats_data
            if statistics is not None:
                result["progress"] = statistics.to_dict()
        return result
