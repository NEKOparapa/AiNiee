"""Own all mutable project state and task execution in the service process."""
import copy
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from Backend.application.status import WorkStatus, build_status_response
from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.core.protocol import to_wire
from Backend.infrastructure.config.store import ConfigStore
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
        self.last_operation = None
        self.network = ProxySettings()
        self._started = False
        self._operation_source = None
        self._operation_name = None
        self._operation_context = None
        self._operation_done = threading.Event()
        self._operation_done.set()
        self._pipeline_progress = {}

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
        self.cache = CacheManager(on_saved=lambda data: self.notify("project.saved", data))
        self.reader = FileReader()
        self.executor = TaskExecutor(self.cache, self.reader, FileOutputer())
        self.simple = SimpleExecutor()
        self.logs = get_gui_handler()
        self.logs.subscribe(self.on_log)
        self._started = True

    def on_log(self, line, level, style="", rows=None):
        self._publish({"type": "log", "line": line, "level": level, "style": style, "rows": rows})

    def _publish(self, message):
        # Disconnected or failing observers cannot change a business outcome.
        try:
            self.publish(to_wire(message))
        except Exception:
            pass

    def notify(self, name, data):
        self._publish({"type": "notification", "name": name, "data": data})

    def _commit_table_result(self, data, view):
        for index, text in data.get("updated_items", {}).items():
            self.cache.update_generated_translation(
                data["file_path"], int(index), text, data.get("translation_status", 1),
            )
        self.cache.save_to_file()
        self.notify("table.updated", {**data, "view": view})

    def _commit_glossary_result(self, request, result):
        if result.get("status") not in ("success", "partial", "cancelled", "stopped"):
            return
        original_rows = {row["src"]: row for row in request.get("prompt_dictionary_data", []) if row.get("src") and not row.get("dst")}
        translations = {row["src"]: row["dst"] for row in result.get("updated_data", []) or [] if row.get("src") and row.get("dst")}
        if not translations:
            return
        def update(config):
            table = next((table for table in config.get("prompt_dictionary_tables", []) if table["id"] == request.get("table_id")), None)
            if table is not None:
                for row in table["rows"]:
                    source = row.get("src")
                    if source in translations and row == original_rows.get(source):
                        row["dst"] = translations[source]
        self.update_config(update)

    def status(self):
        work_status = WorkStatus.IDLE
        if self.busy:
            work_status = {
                "analysis": WorkStatus.ANALYSIS, "api_test": WorkStatus.API_TEST,
                "glossary.translate": WorkStatus.GLOSSARY,
                "table.translate": WorkStatus.TABLE, "table.polish": WorkStatus.TABLE,
                "table.proofread": WorkStatus.TABLE,
            }.get(self._operation_name, WorkStatus.TASKING)
            if self._operation_context is not None and self._operation_context.is_cancelled():
                work_status = WorkStatus.STOPPING
        result = build_status_response(
            self.cache, work_status,
            advance_elapsed=self._operation_name == "translation"
            and getattr(getattr(self, "executor", None), "translation_clock_running", False),
        )
        result["busy"] = self.busy
        result["last_error"] = self.last_error
        result["last_operation"] = self.last_operation
        result["operation"] = (
            {"source": self._operation_source, "name": self._operation_name}
            if self.busy else None
        )
        if self._operation_source == "api":
            result["pipeline_progress"] = dict(self._pipeline_progress)
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

    @contextmanager
    def operation(self, name, *, source="api", context=None):
        """Reserve one top-level operation; its batches may use many threads.

        The lock protects admission only. Never hold it while doing model or
        file I/O: health/status and competing calls must remain responsive.
        """
        if not self.lock.acquire(blocking=False):
            raise BusyError("后端正在执行操作，请稍后重试")
        try:
            self.ensure_idle()
            self._running = True
            self._operation_source = source
            self._operation_name = name
            self._operation_context = context
            self._pipeline_progress = {}
            self._operation_done.clear()
        finally:
            self.lock.release()
        try:
            yield
        finally:
            with self.lock:
                self._running = False
                self._operation_source = None
                self._operation_name = None
                self._operation_context = None
                self._operation_done.set()

    def pipeline_progress(self, statistics):
        self._pipeline_progress = dict(statistics)

    def snapshot(self):
        with self.cache.file_lock:
            return to_wire(self.cache.project) if self.cache.project else None

    def load_project(self, project_type, input_path, exclude_rule=""):
        with self.operation("read", source="desktop"):
            path = Path(input_path).expanduser().resolve()
            if not path.exists():
                raise ValueError("输入路径不存在（路径必须在后端所在机器上可访问）")
            if project_type not in self.reader.get_support_project_types():
                raise ValueError("不支持的项目类型")
            from Backend.application.read_service import read_legacy_project
            project = read_legacy_project(project_type, str(path), exclude_rule)["model"]
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
        with self.operation("check", source="desktop"):
            result = checkers[kind](self.cache).run_check(params)
            self.cache.save_to_file()
            return {"result": to_wire(result), "project": self.snapshot()}

    def save_project(self):
        with self.lock:
            self.ensure_idle()
            if not self.cache.project:
                raise ValueError("请先加载项目")
            self.cache.save_to_file()
            return self.status()

    def stop(self):
        with self.lock:
            if not self.busy:
                return self.status()
            if self._operation_source != "desktop":
                raise PipelineError("OPERATION_OWNERSHIP", "工作区停止接口不能中断模型接口的操作", 409)
            if self._operation_context is None or self._operation_name == "project.export":
                raise PipelineError("OPERATION_NOT_CANCELLABLE", "当前读取、检查或文件写出操作需等待完成", 409)
            self._operation_context.cancel()
            self._publish({"type": "status", "status": self.status()})
            return self.status()

    def start_translation(self, continue_status=False):
        def action(context):
            self.cache.start_saving()
            return self.executor.translate(continue_status, context=context)
        return self._submit("translation", action, {"continue_status": continue_status})

    def start_analysis(self):
        def action(context):
            result = self.executor.analyze(context=context)
            if result.get("analysis_data") is not None:
                self.cache.set_analysis_data(result["analysis_data"])
                self.cache.save_to_file()
            return result
        return self._submit("analysis", action)

    def start_table_translation(self, data):
        data = copy.deepcopy(data)
        return self._submit("table.translate", lambda context: self.simple.process_table_translation(data, context=context), data)

    def start_table_polishing(self, data):
        data = copy.deepcopy(data)
        return self._submit("table.polish", lambda context: self.simple.process_table_polish(data, context=context), data)

    def start_table_proofreading(self, data):
        data = copy.deepcopy(data)
        return self._submit("table.proofread", lambda context: self.executor.proofread(data, context=context), data)

    def start_glossary_translation(self, data):
        data = copy.deepcopy(data)
        def action(context):
            result = self.simple.glossary_translation(data, context=context)
            self._commit_glossary_result(data, result)
            return result
        return self._submit("glossary.translate", action, data, needs_project=False)

    def start_api_test(self, data):
        data = copy.deepcopy(data)
        return self._submit("api_test", lambda context: self.simple.api_test(data, context=context), data, needs_project=False)

    def start_export(self, data):
        data = copy.deepcopy(data)
        return self._submit("project.export", lambda context: self.executor.export(data), data)

    def _submit(self, name, action, data=None, *, needs_project=True):
        with self.lock:
            self.ensure_idle()
            if needs_project and not self.cache.project:
                raise ValueError("请先加载项目")
            request = copy.deepcopy(data or {})
            if name == "translation" and request.get("continue_status") and self.cache.project.stats_data is None:
                raise ValueError("当前项目没有可继续的任务")
            context = ExecutionContext(source="desktop")
            progress_name = {"translation": "translation.progress", "analysis": "analysis.progress"}.get(name)
            if progress_name:
                context.on_progress = lambda data: self.notify(progress_name, data)
            committed = {}
            if name.startswith("table."):
                view = request.get("view", "basic")
                def commit(result):
                    self._commit_table_result(result, view)
                    committed.setdefault(result["file_path"], {}).update(result.get("updated_items", {}))
                context.on_result = commit
            self.last_error = None
            self.last_operation = None
            self._running = True
            self._operation_source = "desktop"
            self._operation_name = name
            self._operation_context = context
            self._operation_done.clear()
            self._publish({"type": "status", "status": self.status()})
            try:
                self.future = self.pool.submit(self._run_operation, name, action, request, context, committed)
            except Exception:
                self._release_operation()
                raise
            return self.status()

    def _release_operation(self):
        self._running = False
        self._operation_source = self._operation_name = None
        self._operation_context = None
        self._operation_done.set()

    def _run_operation(self, name, action, request, context, committed):
        result = {"status": "cancelled"}
        try:
            if not context.is_cancelled():
                result = action(context) or {"status": "success"}
            if name.startswith("table."):
                updates = dict(result.get("updates_by_file", {}))
                if result.get("updated_items") and result.get("file_path"):
                    updates.setdefault(result["file_path"], {}).update(result["updated_items"])
                for file_path, items in updates.items():
                    missing = {index: text for index, text in items.items()
                               if committed.get(file_path, {}).get(index) != text}
                    if missing:
                        context.on_result({
                            "file_path": file_path, "updated_items": missing, "target_column_index": 2,
                            "translation_status": result.get("translation_status", 1),
                        })
            if name == "api_test" and "status" not in result:
                result["status"] = "partial" if result.get("failure") else "success"
            if context.is_cancelled() and result.get("status") == "success":
                result["status"] = "cancelled"
            report = result.get("report") or {}
            output = result.get("output") or {}
            output_report = output.get("report") or {}
            errors = (result.get("operation_errors") or report.get("operation_errors") or report.get("errors")
                      or output_report.get("operation_errors") or output_report.get("errors"))
            if errors:
                from Backend.core.log_system import redact
                first = errors[0]
                detail = (first.get("message") or first.get("code")) if isinstance(first, dict) else first
                self.last_error = redact(str(detail))
        except Exception as error:
            result = self._operation_failure(name, error)
        finally:
            try:
                self.cache.stop_saving()
                if self.cache.project:
                    self.cache.save_to_file()
            except Exception as error:
                failure = self._operation_failure(name, error)
                if name == "project.export" and ("files" in result or "report" in result):
                    # Exported files remain real even if the subsequent cache save
                    # fails. Keep every per-file outcome and append this failure.
                    report = copy.deepcopy(result.get("report", {}))
                    report.setdefault("operation_errors", []).append({
                        "code": "CACHE_SAVE_FAILED", "message": failure["message"],
                    })
                    result = {**result, "status": "partial" if result.get("files") else "failed",
                              "message": failure["message"], "report": report}
                elif name == "translation" and isinstance(result.get("output"), dict):
                    # The model save can fail after automatic export. Its actual
                    # output report still needs to reach the desktop unchanged.
                    result = {**result, **failure}
                else:
                    result = failure
            with self.lock:
                status = result.get("status", "success")
                if status in ("error", "failed") and not self.last_error:
                    from Backend.core.log_system import redact
                    self.last_error = redact(result.get("message") or "操作未成功完成，请查看日志和结果报告")
                self.last_operation = {"name": name, "status": status}
                self._release_operation()
                self._publish({"type": "settled", "operation": name, "status": self.status()})
                self._notify_completion(name, request, result)
        return result

    def _operation_failure(self, name, error):
        from Backend.core.log_system import redact
        self.last_error = redact(str(error))
        logging.getLogger("AiNiee.backend").exception("操作执行失败：%s", name)
        self._publish({"type": "error", "operation": name, "message": self.last_error})
        if name == "project.export":
            detail = {"code": getattr(error, "code", "EXPORT_FAILED"), "message": self.last_error}
            if isinstance(error, PipelineError) and error.details is not None:
                detail["details"] = error.details
            return {"status": "error", "message": self.last_error, "files": [], "report": {"errors": [detail]}}
        return {"status": "error", "message": self.last_error}

    def _notify_completion(self, name, request, result):
        # Persistence has finished before any completion reaches the desktop.
        payload = {key: value for key, value in result.items() if key != "model"}
        if name == "translation":
            self.notify("translation.stopped", payload)
            output = result.get("output")
            output_succeeded = not isinstance(output, dict) or output.get("status") == "success"
            if result.get("status") in ("success", "partial") and not self.last_error and output_succeeded:
                self.notify("translation.completed", payload)
            if isinstance(output, dict):
                self.notify("project.export.completed", {"files": [], "report": {}, **output})
        elif name == "analysis":
            self.notify("analysis.completed", {"analysis_data": None, **payload})
        elif name.startswith("table."):
            self.notify("table.completed", {
                "file_path": request.get("file_path"), "updated_item_count": 0,
                "operation": name.split(".", 1)[1],
                **payload, "view": request.get("view", "basic"),
            })
        elif name == "glossary.translate":
            self.notify("glossary.completed", {
                "updated_data": None, **payload, "table_id": request.get("table_id"),
                "request_id": request.get("request_id"),
            })
        elif name == "api_test":
            failure = [result.get("message") or "接口测试未完成"] if result.get("status") in ("error", "failed", "cancelled") else []
            self.notify("api_test.completed", {"success": [], "failure": failure, **payload})
        elif name == "project.export":
            self.notify("project.export.completed", {"files": [], "report": {}, **payload})

    def close(self):
        with self.lock:
            self.closing = True
            if self._operation_context is not None and self._operation_name != "project.export":
                self._operation_context.cancel()
        # Both the HTTP worker and the desktop worker must finish before shared
        # clients or caches are disposed. Queued operations are never admitted.
        self._operation_done.wait()
        self.pool.shutdown(wait=True, cancel_futures=True)
        try:
            try:
                if self.cache.project:
                    self.cache.save_to_file()
            finally:
                self.cache.close()
        finally:
            self.executor.close()
            from Backend.infrastructure.llm.llm_client_factory import LLMClientFactory
            LLMClientFactory().close_all_clients()
            self.logs.unsubscribe(self.on_log)
            self.network.close()
            self._started = False
