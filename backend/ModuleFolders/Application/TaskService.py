"""Own the single task lifecycle while reusing the unchanged legacy pipelines."""

from copy import deepcopy
import logging
from threading import Event, RLock, Thread, current_thread

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.OperationGuard import (
    OPERATION_LOCK, claim_background_operation, exclusive_operation, release_background_operation,
)
from ModuleFolders.Application.PlatformService import PlatformService
from ModuleFolders.Application.SettingsDefaults import fill_setting_defaults
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Log.LogSystem import sensitive_values
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.Cache.CacheManager import CacheManager


STATUS_NAMES = {
    Base.STATUS.IDLE: "idle", Base.STATUS.TASKING: "running", Base.STATUS.STOPING: "stopping",
    Base.STATUS.TASKSTOPPED: "stopped", Base.STATUS.API_TEST: "api_test", Base.STATUS.GLOSS_TASK: "glossary",
    Base.STATUS.ANALYSIS_TASK: "analysis", Base.STATUS.TABLE_TASK: "table",
}

_logger = logging.getLogger("AiNiee.tasks")


class TaskService(ConfigMixin):
    def __init__(self, cache_manager: CacheManager, task_executor=None) -> None:
        self.cache_manager = cache_manager
        self.task_executor = task_executor
        self._lock = RLock()
        self._worker = None
        self._active = False
        self._closed = False
        self._mode = None
        self._project_id = None
        self._status = None
        self._stop_requested = False
        self._last_error = None
        self._analysis_progress = None
        self._completed = False
        self._manager = EventManager.get_singleton()
        self._events = (Base.EVENT.TASK_UPDATE, Base.EVENT.TASK_COMPLETED,
                        Base.EVENT.ANALYSIS_TASK_UPDATE, Base.EVENT.ANALYSIS_TASK_DONE)
        if task_executor is not None:
            for event in self._events:
                self._manager.subscribe(event, self._on_event)

    def get_current(self) -> dict:
        with self._lock:
            active, task_project_id, task_mode, status, last_error, analysis = (
                self._active, self._project_id, self._mode, self._status,
                self._last_error, deepcopy(self._analysis_progress),
            )
        # Never hold the controller lock while waiting for legacy cache locks:
        # legacy callbacks can arrive from threads that already own cache data.
        with self.cache_manager.file_lock:
            project = self.cache_manager.project
        result = {"status": STATUS_NAMES.get(Base.work_status, "unknown"),
                  "project_id": None, "project_name": None, "progress": {}}
        if project is not None:
            with project.atomic_scope():
                result["project_id"] = project.project_id or None
                result["project_name"] = project.project_name or None
                statistics = project.stats_data
            if statistics is not None:
                result["progress"] = statistics.to_dict()
        # Keep the M2 read-only view usable by lightweight runtime adapters.
        if self.task_executor is None:
            return result
        same_project = project is not None and project.project_id == task_project_id
        mode = task_mode if same_project else None
        if active or (same_project and Base.work_status in (Base.STATUS.IDLE, Base.STATUS.TASKSTOPPED)):
            result["status"] = status or result["status"]
        pending = TranslationStatus.TRANSLATED if mode == "polish" else TranslationStatus.UNTRANSLATED
        can_continue = bool(
            not active and project is not None and mode != "analysis"
            and project.stats_data is not None and project.count_items(pending) > 0
            and (same_project or result["progress"].get("line", 0) > 0)
        )
        result.update(mode=mode, can_continue=can_continue,
                      last_error=last_error if same_project else None,
                      analysis_progress=analysis if same_project else None)
        return result

    def translate(self, continue_task: bool = False) -> dict:
        return self._start("translate", continue_task)

    def polish(self, continue_task: bool = False) -> dict:
        return self._start("polish", continue_task)

    def analysis(self) -> dict:
        return self._start("analysis", False)

    def _start(self, mode: str, continue_task: bool) -> dict:
        with exclusive_operation(), self._lock:
            if self._closed or self.task_executor is None:
                raise ApplicationError("task_service_unavailable", 503)
            project = self.cache_manager.project
            if project is None:
                raise ApplicationError("project_not_open", 409)
            pending = TranslationStatus.TRANSLATED if mode == "polish" else TranslationStatus.UNTRANSLATED
            if mode != "analysis" and project.count_items(pending) == 0:
                raise ApplicationError("task_no_pending_items", 409)
            if continue_task and project.stats_data is None:
                raise ApplicationError("task_cannot_continue", 409)
            # Qt settings pages persisted defaults before the legacy task ran.
            self.update_config(lambda config: config.update(fill_setting_defaults(config)))
            config = TaskConfig()
            config.initialize("extract" if mode == "analysis" else mode)
            if config.get_active_platform_tag("extract" if mode == "analysis" else mode) is None:
                raise ApplicationError("task_platform_required", 409)
            if not getattr(config, "label_input_path", None):
                self.update_config(lambda values: values.update(label_input_path=project.input_path))
            try:
                self.cache_manager.save_to_file()
            except Exception as error:
                raise ApplicationError("cache_save_failed", 500) from error
            self._mode = mode
            self._project_id = project.project_id
            self._status = "analysis" if mode == "analysis" else "running"
            self._last_error = None
            self._analysis_progress = None
            self._stop_requested = False
            self._completed = False
            self._active = True
            claim_background_operation(self)
            Base.work_status = Base.STATUS.ANALYSIS_TASK if mode == "analysis" else Base.STATUS.TASKING
            worker = Thread(target=self._run, args=(mode, continue_task), name=f"ainiee-{mode}", daemon=True)
            self._worker = worker
            try:
                worker.start()
            except Exception:
                self._active = False
                self._status = "failed"
                self._last_error = "task_start_failed"
                Base.work_status = Base.STATUS.IDLE
                release_background_operation(self)
                raise ApplicationError("task_start_failed", 500) from None
        self._notify()
        return self.get_current()

    def stop(self) -> dict:
        with OPERATION_LOCK, self._lock:
            if self._active:
                self._stop_requested = True
                self._status = "stopping"
                Base.work_status = Base.STATUS.STOPING
                self._cancel_requests()
        self._notify()
        return self.get_current()

    def _cancel_requests(self) -> None:
        from ModuleFolders.Infrastructure.LLMRequester.LLMClientFactory import LLMClientFactory

        self.task_executor._cancel_active_executor()
        LLMClientFactory().close_all_clients()

    def _run(self, mode: str, continue_task: bool) -> None:
        save_stop = Event()
        saver = Thread(target=self._save_periodically, args=(save_stop,), name="ainiee-cache-save", daemon=True)
        secrets = []
        try:
            saver.start()
            with self._lock:
                stopped_before_entry = self._stop_requested
            if not stopped_before_entry:
                # Legacy worker exceptions are never returned verbatim to HTTP.
                secrets = self._platform_secrets()
                with sensitive_values(secrets, across_threads=True):
                    if mode == "analysis":
                        self.task_executor.analysis_start_target()
                    elif mode == "polish":
                        self.task_executor.polish_start_target(continue_task)
                    else:
                        self.task_executor.translation_start_target(continue_task)
        except Exception:
            with sensitive_values(secrets, across_threads=True):
                _logger.exception("Task execution failed (%s)", mode)
            with self._lock:
                if not self._stop_requested:
                    self._last_error = "task_execution_failed"
            self._cancel_requests()
        finally:
            save_stop.set()
            if saver.ident is not None:
                saver.join()
            try:
                self.cache_manager.save_to_file()
            except Exception:
                _logger.exception("Project cache save failed while finishing a task")
                with self._lock:
                    self._last_error = "cache_save_failed"
            with OPERATION_LOCK, self._lock:
                if self._last_error:
                    self._status = "failed"
                elif self._stop_requested:
                    self._status = "stopped"
                elif self._completed:
                    self._status = "completed"
                else:
                    self._status = "failed"
                    self._last_error = "task_execution_failed"
                self._active = False
                Base.work_status = Base.STATUS.IDLE
                release_background_operation(self)
            self._notify()
            if self._closed:
                self._unsubscribe()

    def _platform_secrets(self) -> list[str]:
        result = []
        for platform in self.load_config().get("platforms", {}).values():
            result.extend(PlatformService._secrets(platform))
        return result

    def _save_periodically(self, stop: Event) -> None:
        while not stop.wait(self.cache_manager.SAVE_INTERVAL):
            if self.cache_manager.save_to_file_require_flag:
                try:
                    self.cache_manager.save_to_file()
                except Exception:
                    _logger.exception("Project cache autosave failed")
                    with self._lock:
                        self._last_error = "cache_save_failed"

    def _on_event(self, event: int, data: dict) -> None:
        with self._lock:
            if not self._active:
                return
            # Targets reset Base status on entry; restore a stop received before
            # their first update, before any request can be submitted.
            if self._stop_requested:
                Base.work_status = Base.STATUS.STOPING
            if event == Base.EVENT.TASK_COMPLETED:
                self._completed = True
            elif event == Base.EVENT.ANALYSIS_TASK_UPDATE:
                self._analysis_progress = {key: deepcopy(data[key]) for key in (
                    "status", "phase", "phase_label", "current", "total", "percent", "message", "detail"
                ) if key in data}
            elif event == Base.EVENT.ANALYSIS_TASK_DONE:
                self._completed = data.get("status") == "success"
                if data.get("status") == "error" and not self._stop_requested:
                    self._last_error = "task_execution_failed"

    def _notify(self) -> None:
        self._manager.emit(Base.EVENT.TASK_STATE_CHANGED, {})

    def wait(self, timeout: float | None = None) -> bool:
        with self._lock:
            worker = self._worker
        if worker is not None and worker is not current_thread() and worker.ident is not None:
            worker.join(timeout)
        return worker is None or not worker.is_alive()

    def _unsubscribe(self) -> None:
        for event in self._events:
            self._manager.unsubscribe(event, self._on_event)

    def close(self, timeout: float | None = 10) -> bool:
        with self._lock:
            self._closed = True
        if self.task_executor is not None:
            self.stop()
        done = self.wait(timeout)
        if done:
            self._unsubscribe()
        return done
