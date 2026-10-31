"""Own all mutable project state and task execution in the service process."""
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from Backend.application.status import build_status_response
from Backend.core.protocol import COMMANDS, NOTIFICATIONS, TABLE_UPDATES, TERMINAL_EVENTS, command_failure, to_wire
from Backend.core.base import Base
from Backend.core.events import EventManager
from Backend.infrastructure.config.store import ConfigStore
from Backend.domain.config.task_type import TaskType
from Backend.infrastructure.network import ProxySettings


class BusyError(ValueError):
    pass


class Runtime(ConfigStore):
    CACHE_METHODS = frozenset((
        "list_project_histories", "delete_project_cache", "load_from_project_id",
        "load_from_file", "save_to_file", "reset_project_status", "set_analysis_data",
        "clear_analysis_data", "update_item_text", "update_generated_translation",
        "search_items",
    ))

    def __init__(self):
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backend-task")
        self.future = None
        self.publish = lambda message: None
        self.closing = False
        self.last_error = None
        self._running = False
        self._terminal_events = []
        self._command_data = {}
        self.network = ProxySettings()
        self._started = False

    def save_config(self, new, *, _table_update=False):
        config = super().save_config(new, _table_update=_table_update)
        if self.network.apply(config) and self._started:
            # Existing SDK clients retain transports created with the old proxy.
            from Backend.infrastructure.llm.llm_client_factory import LLMClientFactory
            LLMClientFactory().close_all_clients()
        return config

    def start(self):
        from Backend.core.platform.runtime_setup import ensure_user_dirs
        from Backend.infrastructure.cache import CacheManager
        from Backend.infrastructure.files.readers.file_reader import FileReader
        from Backend.infrastructure.files.writers.file_outputer import FileOutputer
        from Backend.application.tasks.task_executor import TaskExecutor
        from Backend.application.simple_executor import SimpleExecutor
        from Backend.core.log_system import get_gui_handler

        ensure_user_dirs()
        self.initialize_config()
        from Backend.infrastructure.tokenizers.tiktoken_loader import initialize_tiktoken
        try:
            initialize_tiktoken()
        except Exception:
            logging.getLogger("AiNiee.backend").warning("Token 编码器初始化失败，可切换到行数限制模式", exc_info=True)
        self.cache = CacheManager()
        self.reader = FileReader()
        self.executor = TaskExecutor(self.cache, self.reader, FileOutputer())
        self.simple = SimpleExecutor()
        # Commands are admitted and serialized here, rather than starting untracked threads.
        self.executor._cleanup_event_subscriptions()
        self.simple._cleanup_event_subscriptions()
        self.events = EventManager.get_singleton()
        for event in NOTIFICATIONS:
            self.events.subscribe(event, self.on_event)
        self.logs = get_gui_handler()
        self.logs.subscribe(self.on_log)
        Base.work_status = Base.STATUS.IDLE
        self._started = True

    def on_log(self, line, level, style="", rows=None):
        self.publish({"type": "log", "line": line, "level": level, "style": style, "rows": rows})

    def on_event(self, event, data):
        if event in TABLE_UPDATES:
            # Results must survive even when no desktop client is connected.
            for index, text in data.get("updated_items", {}).items():
                self.cache.update_generated_translation(
                    data["file_path"], int(index), text, data.get("translation_status", 1),
                )
            self.cache.save_to_file()
        if event == Base.EVENT.GLOSS_TASK_DONE and self._running and data.get("status") in ("success", "partial"):
            original_rows = {row["src"]: row for row in self._command_data.get("prompt_dictionary_data", []) if row.get("src") and not row.get("dst")}
            translations = {row["src"]: row["dst"] for row in data.get("updated_data", []) or [] if row.get("src") and row.get("dst")}
            def update(config):
                table = next((table for table in config.get("prompt_dictionary_tables", []) if table["id"] == data.get("table_id")), None)
                if table is not None:
                    for row in table["rows"]:
                        source = row.get("src")
                        if source in translations and row == original_rows.get(source):
                            row["dst"] = translations[source]
            self.update_config(update)
        if event in TERMINAL_EVENTS and self._running:
            self._terminal_events.append((event, to_wire(data)))
            return
        self.publish({"type": "event", "event": event, "data": to_wire(data)})

    def status(self):
        result = build_status_response(self.cache)
        # The desktop historically turns TASKSTOPPED into IDLE in its event handler.
        # That transition is now owned by the backend, too.
        result["busy"] = self.busy
        result["last_error"] = self.last_error
        result["active_workers"] = sum(
            thread.name.startswith(("translator", "polisher", "proofreader", "analysis_stage"))
            for thread in threading.enumerate()
        ) if self.busy else 0
        if self.cache.project and self.cache.project.stats_data:
            result["stats"] = self.cache.project.stats_data.to_dict()
        else:
            result["stats"] = {}
        return result

    @property
    def busy(self):
        return self._running

    def ensure_idle(self):
        if self.closing or self.busy:
            raise BusyError("后端正在执行任务，请先停止或等待任务完成")

    def snapshot(self):
        with self.cache.file_lock:
            return to_wire(self.cache.project) if self.cache.project else None

    def load_project(self, project_type, input_path, exclude_rule=""):
        with self.lock:
            self.ensure_idle()
            path = Path(input_path).expanduser().resolve()
            if not path.is_dir():
                raise ValueError("输入目录不存在（路径必须在后端所在机器上可访问）")
            if project_type not in self.reader.get_support_project_types():
                raise ValueError("不支持的项目类型")
            project = self.reader.read_files(project_type, str(path), exclude_rule)
            if project is None or project.count_items() == 0:
                raise ValueError("项目为空，请检查输入目录和项目类型")
            self.cache.load_from_project(project)
            self.cache.save_to_file()
            self.save_config({"label_input_path": str(path), "translation_project": project_type})
            return self.snapshot()

    def cache_call(self, method, args, kwargs, project_id=None):
        if method not in self.CACHE_METHODS:
            raise ValueError("不支持的缓存操作")
        with self.lock:
            if method == "list_project_histories":
                # A reconnect may read history during a task, but cannot prune.
                if self.busy:
                    args = list(args)
                    if len(args) > 1:
                        args[1] = False
                    else:
                        kwargs = {**kwargs, "prune": False}
            else:
                self.ensure_idle()
            if method in ("load_from_project_id", "delete_project_cache"):
                identifier = args[0] if args else kwargs.get("project_id", "")
                if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
                    raise ValueError("无效的项目 ID")
            if method not in ("list_project_histories", "load_from_project_id", "load_from_file", "delete_project_cache"):
                current_id = self.cache.project.project_id if self.cache.project else None
                if project_id != current_id:
                    raise BusyError("项目已切换，请刷新后重试")
            import inspect
            try:
                inspect.signature(getattr(self.cache, method)).bind(*args, **kwargs)
            except TypeError as error:
                raise ValueError("缓存操作参数不正确") from error
            result = getattr(self.cache, method)(*args, **kwargs)
            if method == "delete_project_cache" and result and self.cache.project and self.cache.project.project_id == identifier:
                self.cache.project = None
            if method in ("update_item_text", "update_generated_translation", "set_analysis_data", "clear_analysis_data"):
                self.cache.save_to_file()
            return {"result": to_wire(result), "project": self.snapshot()}

    def check(self, kind, params):
        from Backend.application.checks.language_checker import LanguageChecker
        from Backend.application.checks.rule_checker import RuleChecker
        from Backend.application.checks.terminology_checker import TerminologyChecker
        checkers = {"language": LanguageChecker, "rule": RuleChecker, "terminology": TerminologyChecker}
        if kind not in checkers:
            raise ValueError("未知检查类型")
        with self.lock:
            self.ensure_idle()
            result = checkers[kind](self.cache).run_check(params)
            self.cache.save_to_file()
            return {"result": to_wire(result), "project": self.snapshot()}

    def command(self, event, data):
        if event not in COMMANDS:
            raise ValueError("不支持的任务指令")
        with self.lock:
            if event == Base.EVENT.TASK_STOP:
                if self.busy:
                    Base.work_status = Base.STATUS.STOPING
                    self.executor._cancel_active_executor()
                    from Backend.infrastructure.llm.llm_client_factory import LLMClientFactory
                    LLMClientFactory().close_all_clients()
                self.publish({"type": "status", "status": self.status()})
                return self.status()
            self.ensure_idle()
            if event not in (Base.EVENT.API_TEST_START, Base.EVENT.GLOSS_TASK_START) and not self.cache.project:
                raise ValueError("请先加载项目")
            if event == Base.EVENT.TASK_MANUAL_SAVE_CACHE:
                self.cache.save_to_file()
                return self.status()
            # Do not accept arbitrary event numbers to broadcast as task results.
            if "update_event" in data and data["update_event"] not in TABLE_UPDATES:
                raise ValueError("无效的表格更新事件")
            from Backend.core.protocol import TABLE_DONE
            if data.get("done_event") is not None and data["done_event"] not in TABLE_DONE:
                raise ValueError("无效的表格完成事件")
            if event == Base.EVENT.TASK_START:
                mode = data.get("current_mode")
                if mode not in (TaskType.TRANSLATION, TaskType.POLISH):
                    raise ValueError("无效的任务类型")
                if data.get("continue_status") and self.cache.project.stats_data is None:
                    raise ValueError("当前项目没有可继续的任务")
            self.last_error = None
            self._terminal_events = []
            self._command_data = data
            self._running = True
            Base.work_status = {
                Base.EVENT.ANALYSIS_TASK_START: Base.STATUS.ANALYSIS_TASK,
                Base.EVENT.API_TEST_START: Base.STATUS.API_TEST,
                Base.EVENT.GLOSS_TASK_START: Base.STATUS.GLOSS_TASK,
            }.get(event, Base.STATUS.TASKING if event == Base.EVENT.TASK_START else Base.STATUS.TABLE_TASK)
            self.publish({"type": "status", "status": self.status()})
            self.future = self.pool.submit(self._run, event, data)
            return self.status()

    def _run(self, event, data):
        try:
            if Base.work_status == Base.STATUS.STOPING:
                return
            E = Base.EVENT
            if event == E.TASK_START:
                self.cache.start_interval_saving(event, data)
                target = self.executor.translation_start_target if data["current_mode"] == TaskType.TRANSLATION else self.executor.polish_start_target
                target(bool(data.get("continue_status")))
            elif event == E.ANALYSIS_TASK_START:
                self.executor.analysis_start_target()
            elif event == E.TABLE_PROOFREAD_START:
                self.executor.table_proofread_start_target(data)
            elif event == E.TABLE_TRANSLATE_START:
                self.simple.process_table_translation(data)
            elif event == E.TABLE_POLISH_START:
                self.simple.process_table_polish(data)
            elif event == E.API_TEST_START:
                self.simple.api_test(event, data)
            elif event == E.GLOSS_TASK_START:
                self.simple.glossary_translation(event, data)
            elif event == E.TASK_MANUAL_EXPORT:
                if self.executor.task_manual_export(event, data) is False:
                    raise ValueError("导出失败，详情请查看后端日志")
        except Exception as error:
            from Backend.core.log_system import redact
            self.last_error = redact(str(error))
            logging.getLogger("AiNiee.backend").exception("任务执行失败")
            self.publish({"type": "error", "event": event, "message": self.last_error})
            failure = command_failure(event, data, self.last_error)
            if failure is not None:
                self.on_event(*failure)
        finally:
            try:
                self.cache.save_to_file()
            finally:
                with self.lock:
                    Base.work_status = Base.STATUS.IDLE
                    self._running = False
                    pending = self._terminal_events
                    self._terminal_events = []
                    self.publish({"type": "settled", "event": event, "status": self.status()})
                    for completed_event, completed_data in pending:
                        self.on_event(completed_event, completed_data)

    def close(self):
        self.closing = True
        if self.busy:
            Base.work_status = Base.STATUS.STOPING
            self.executor._cancel_active_executor()
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.cache.app_shut_down(Base.EVENT.APP_SHUT_DOWN, {})
        self.cache.save_to_file()
        self.executor.app_shut_down(Base.EVENT.APP_SHUT_DOWN, {})
        for event in NOTIFICATIONS:
            self.events.unsubscribe(event, self.on_event)
        self.cache._cleanup_event_subscriptions()
        self.logs.unsubscribe(self.on_log)
        self.network.close()
        self._started = False
        Base.work_status = Base.STATUS.IDLE
