"""Project services backed by three independent, serial task queues."""
import copy
import logging
import re
import threading
from pathlib import Path
from uuid import uuid4

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

    def __init__(self, *, job_store_path=None):
        self.lock = threading.RLock()
        self._scheduler = None
        self._job_store_path = job_store_path
        self._desktop_requests = {}
        self._pending_network_config = None
        self.publish = lambda message: None
        self.closing = False
        self.last_error = None
        self.last_operation = None
        self.network = ProxySettings()
        self._started = False
        self._mcp_enabled = True

    @property
    def mcp_enabled(self):
        # A live service switch, separate from per-job configuration snapshots.
        # Read the scalar without blocking the ASGI event loop on job locks.
        return self._mcp_enabled

    @property
    def scheduler(self):
        # Keep importing the ASGI application free of filesystem side effects.
        with self.lock:
            if self._scheduler is None:
                from Backend.application.job_scheduler import JobScheduler
                from Backend.core.paths import cache_root
                self._scheduler = JobScheduler(
                    self._job_store_path or cache_root() / "tasks.sqlite3",
                    on_event=self._on_job_event,
                )
            return self._scheduler

    def save_config(self, new, *, _table_update=False):
        with self.lock:
            config = super().save_config(new, _table_update=_table_update)
            self._validate_mcp_settings(config)
            self._mcp_enabled = config.get("mcp_enable", True)
            desired_proxy = str(config.get("proxy_url") or "").strip() if config.get("proxy_enable") else ""
            self._pending_network_config = config if desired_proxy != self.network.current else None
            self._apply_pending_network()
            return config

    def update_config(self, updater):
        # Always acquire Runtime before CONFIG_FILE_LOCK, including callbacks
        # that merge glossary results into the latest saved configuration.
        with self.lock:
            return super().update_config(updater)

    def _apply_pending_network(self):
        """Environment proxies and cached transports change only between jobs."""
        if self._pending_network_config is None or self.busy:
            return
        if self.network.apply(self._pending_network_config) and self._started:
            from Backend.infrastructure.llm.llm_client_factory import LLMClientFactory
            LLMClientFactory().close_all_clients()
        self._pending_network_config = None

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
        self.scheduler

    def on_log(self, line, level, style="", rows=None):
        self._publish({"type": "log", "line": line, "level": level, "style": style, "rows": rows})

    def _publish(self, message):
        # Disconnected or failing observers cannot change a business outcome.
        try:
            self.publish(to_wire(message))
        except Exception:
            pass

    def notify(self, name, data, *, job=None):
        if job is None:
            current = self._scheduler.current_job() if self._scheduler is not None else None
            job = {"id": current.id, "lane": current.lane, "project_id": current.project_id} if current else None
        identifiers = {"job_id": job["id"], "lane": job["lane"], "project_id": job.get("project_id")} if job else {}
        self._publish({"type": "notification", "name": name, "data": data, **identifiers})

    def _on_job_event(self, job):
        # Models can be large. WebSocket events carry metadata; GET /api/jobs/id
        # retrieves the result. The scheduler never calls us with its lock held.
        self._publish({"type": "job", "job": {key: value for key, value in job.items() if key != "result"}})
        terminal = job["state"] in {"succeeded", "partial", "failed", "cancelled", "interrupted"}
        with self.lock:
            request = self._desktop_requests.pop(job["id"], None) if terminal else None
            if request is not None:
                result = job.get("result") or {"status": "cancelled" if job["state"] == "cancelled" else "error",
                                               "message": (job.get("error") or {}).get("message", "任务未完成")}
                self.last_operation = {"name": job["name"], "status": result.get("status", job["state"]), "job_id": job["id"]}
                if job["state"] == "failed" and not self.last_error:
                    self.last_error = (job.get("error") or {}).get("message") or result.get("message", "任务执行失败")
                self._publish({"type": "settled", "operation": job["name"], "job_id": job["id"],
                               "lane": job["lane"], "status": self.status()})
                self._notify_completion(job["name"], request, result, job=job)
            elif self._started and job["lane"] == "document":
                self._publish({"type": "status", "status": self.status()})
            if terminal:
                self._apply_pending_network()

    @staticmethod
    def lane_for_model(model):
        """Infer ownership from model contents, never a client-selected lane."""
        if hasattr(model, "to_dict"):
            model = model.to_dict()
        kinds = set()
        def category(value):
            return value if value in ("image", "audio") else "document"
        declared = str(model.get("project_type", "")).lower()
        if declared:
            kinds.add(category(declared))
        for file in model.get("files", {}).values():
            media = str(file.get("media_type", "")).lower()
            file_type = str(file.get("file_project_type", "")).lower()
            for value in (media, file_type):
                if value:
                    kinds.add(category(value))
            for item in file.get("items", []):
                locator_kind = (item.get("locator") or {}).get("kind")
                if locator_kind:
                    kinds.add(category(locator_kind))
        if len(kinds) > 1:
            raise PipelineError("MIXED_PROJECT_KINDS", "文档、图片、音频请分别创建项目后提交任务", 422)
        return next(iter(kinds), "document")

    def run_job(self, name, action, *, lane="document", source="api", context=None,
                operation_id=None, project_id=None, background=False):
        from Backend.core.config import config_snapshot
        if self._scheduler is not None and self._scheduler.current_job() is not None:
            raise PipelineError("NESTED_JOB", "任务内部应直接调用服务，不能再次提交队列任务", 409)
        with self.lock:
            if self.closing:
                raise PipelineError("BACKEND_CLOSING", "后端正在关闭，不再接收新任务", 503)
            snapshot = copy.deepcopy(self.load_config())
            context = context or ExecutionContext(source=source)
            context.source = source
            def execute(job_context):
                with config_snapshot(snapshot):
                    return action(job_context)
            job = self.scheduler.submit(lane, name, execute, source=source, context=context,
                                        job_id=operation_id, project_id=project_id)
        if background:
            return job.to_dict()
        # Waiting never holds the Runtime lock: queries, cancellation and other
        # lanes must remain available while the task runs or waits in its queue.
        from concurrent.futures import CancelledError
        try:
            return job.future.result()
        except CancelledError as error:
            raise PipelineError("JOB_CANCELLED", "排队任务已取消", 409) from error

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
        queues = self._scheduler.lanes() if self._scheduler is not None else {
            lane: {"running": None, "queued": []} for lane in ("document", "image", "audio")
        }
        document = queues["document"]
        operation = document["running"] or next(iter(document["queued"]), None)
        work_status = WorkStatus.IDLE
        if operation:
            work_status = {
                "analysis": WorkStatus.ANALYSIS, "api_test": WorkStatus.API_TEST,
                "glossary.translate": WorkStatus.GLOSSARY,
                "table.translate": WorkStatus.TABLE, "table.polish": WorkStatus.TABLE,
                "table.proofread": WorkStatus.TABLE,
            }.get(operation["name"], WorkStatus.TASKING)
            if operation["state"] == "cancelling":
                work_status = WorkStatus.STOPPING
        result = build_status_response(
            getattr(self, "cache", None), work_status,
            advance_elapsed=bool(operation and operation["name"] == "translation")
            and getattr(getattr(self, "executor", None), "translation_clock_running", False),
        )
        # Legacy desktop fields belong to the document workspace. Media pages
        # query their job IDs; they must not disable document controls.
        result["busy"] = bool(operation)
        result["any_busy"] = any(queue["running"] or queue["queued"] for queue in queues.values())
        result["queues"] = queues
        result["network_settings_pending"] = self._pending_network_config is not None
        result["last_error"] = self.last_error
        result["last_operation"] = self.last_operation
        result["operation"] = (
            {key: operation[key] for key in ("source", "name", "id", "lane", "state")}
            if operation else None
        )
        if operation and operation["source"] in ("api", "mcp"):
            result["pipeline_progress"] = dict(operation.get("progress", {}))
        result["active_workers"] = sum(
            thread.name.startswith(("translator", "polisher", "proofreader", "analysis_stage"))
            for thread in threading.enumerate()
        ) if operation else 0
        project = getattr(getattr(self, "cache", None), "project", None)
        if project and project.stats_data:
            result["stats"] = project.stats_data.to_dict()
        else:
            result["stats"] = {}
        return result

    @property
    def busy(self):
        return self._scheduler is not None and any(
            queue["running"] or queue["queued"] for queue in self._scheduler.lanes().values()
        )

    def pipeline_progress(self, statistics):
        job = self.scheduler.current_job()
        if job:
            self.scheduler.update_progress(job.id, statistics)

    def snapshot(self):
        with self.cache.file_lock:
            return to_wire(self.cache.project) if self.cache.project else None

    def load_project(self, project_type, input_path, exclude_rule=""):
        def load(context):
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
        return self.run_job("read", load, source="desktop")

    def cache_call(self, method, args, kwargs, project_id=None):
        if method not in self.CACHE_METHODS:
            raise ValueError("不支持的缓存操作")
        args, kwargs = copy.deepcopy(args), copy.deepcopy(kwargs)
        if method == "search_items":
            import inspect
            kwargs["expected_project_id"] = project_id
            try:
                inspect.signature(self.cache.search_items_snapshot).bind(*args, **kwargs)
            except TypeError as error:
                raise ValueError("缓存操作参数不正确") from error
            return self.cache.search_items_snapshot(*args, **kwargs)
        if method == "list_project_histories":
            # History is a query. Pruning is deliberately excluded from it;
            # deletion has its own queued mutation.
            args = list(args)
            if len(args) > 1:
                args[1] = False
            else:
                kwargs["prune"] = False
        def call(context=None):
            if method in ("load_from_project_id", "delete_project_cache"):
                identifier = args[0] if args else kwargs.get("project_id", "")
                if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
                    raise ValueError("无效的项目 ID")
            if method not in ("list_project_histories", "load_from_project_id", "load_from_file", "delete_project_cache"):
                current_id = self.cache.project.project_id if self.cache.project else None
                if project_id != current_id:
                    raise PipelineError("PROJECT_CHANGED", "项目已切换，请刷新后重试", 409)
            import inspect
            try:
                inspect.signature(getattr(self.cache, method)).bind(*args, **kwargs)
            except TypeError as error:
                raise ValueError("缓存操作参数不正确") from error
            result = getattr(self.cache, method)(*args, **kwargs)
            if method == "delete_project_cache" and result:
                with self.cache.file_lock:
                    if self.cache.project and self.cache.project.project_id == identifier:
                        self.cache.project = None
            if method in ("update_item_text", "update_generated_translation", "set_analysis_data", "clear_analysis_data"):
                self.cache.save_to_file()
            return {"result": to_wire(result), "project": self.snapshot()}
        if method == "list_project_histories":
            return call()
        return self.run_job(f"cache/{method}", call, source="desktop", project_id=project_id)

    def check(self, kind, params):
        from Backend.application.checks.language_checker import LanguageChecker
        from Backend.application.checks.rule_checker import RuleChecker
        from Backend.application.checks.terminology_checker import TerminologyChecker
        checkers = {"language": LanguageChecker, "rule": RuleChecker, "terminology": TerminologyChecker}
        if kind not in checkers:
            raise ValueError("未知检查类型")
        project_id = self.snapshot_id()
        def check(context):
            self._require_project(project_id)
            result = checkers[kind](self.cache).run_check(params)
            self.cache.save_to_file()
            return {"result": to_wire(result), "project": self.snapshot()}
        return self.run_job("check", check, source="desktop", project_id=project_id)

    def save_project(self):
        project_id = self.snapshot_id()
        def save(context):
            self._require_project(project_id)
            self.cache.save_to_file()
        self.run_job("project.save", save, source="desktop", project_id=project_id)
        return self.status()

    def snapshot_id(self):
        with self.cache.file_lock:
            return self.cache.project.project_id if self.cache.project else None

    def _require_project(self, project_id):
        if not project_id:
            raise ValueError("请先加载项目")
        if self.snapshot_id() != project_id:
            raise PipelineError("PROJECT_CHANGED", "排队期间项目已切换，请在原项目中重新提交任务", 409)

    def stop(self):
        # This legacy control belongs to the document page. Never stop an image
        # or audio task just because it happened to be running at the same time.
        queue = self.scheduler.lanes()["document"]
        running = queue["running"]
        candidates = ([running] if running else []) + queue["queued"]
        owned = [job for job in candidates if job["source"] == "desktop"]
        if not owned and running:
            raise PipelineError("OPERATION_OWNERSHIP", "工作区停止接口不能中断模型接口的操作", 409)
        if owned:
            self.scheduler.cancel(owned[0]["id"])
        return self.status()

    def stop_model_operation(self, operation_id):
        """Cancel only the explicitly identified model call, never another page."""
        try:
            job = self.scheduler.get(operation_id)
        except PipelineError as error:
            if error.code != "JOB_NOT_FOUND":
                raise
            # The media page can click Stop before its POST has been admitted.
            # Its bounded retry targets this exact ID; never cancel a different
            # job merely because this one has not appeared yet.
            return {"status": "idle", "operation_id": operation_id}
        if job["source"] != "api":
            raise PipelineError("OPERATION_OWNERSHIP", "此操作不属于模型接口，未停止其他任务", 409)
        job = self.scheduler.cancel(operation_id)
        return {"status": "stopping" if job["state"] == "cancelling" else job["state"],
                "operation_id": operation_id, "job": job}

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
            project_id = self.snapshot_id() if needs_project else None
            if needs_project:
                self._require_project(project_id)
            request = copy.deepcopy(data or {})
            if name == "translation" and request.get("continue_status") and self.cache.project.stats_data is None:
                raise ValueError("当前项目没有可继续的任务")
            context = ExecutionContext(source="desktop")
            progress_name = {"translation": "translation.progress", "analysis": "analysis.progress"}.get(name)
            if progress_name:
                def progress(data):
                    self.pipeline_progress(data)
                    self.notify(progress_name, data)
                context.on_progress = progress
            else:
                context.on_progress = self.pipeline_progress
            committed = {}
            if name.startswith("table."):
                view = request.get("view", "basic")
                def commit(result):
                    self._commit_table_result(result, view)
                    committed.setdefault(result["file_path"], {}).update(result.get("updated_items", {}))
                context.on_result = commit
            identifier = uuid4().hex
            self._desktop_requests[identifier] = request
            def execute(job_context):
                self.last_error = None
                self.last_operation = None
                if needs_project:
                    self._require_project(project_id)
                return self._run_operation(name, action, request, job_context, committed)
            try:
                job = self.run_job(name, execute, source="desktop", context=context,
                                   operation_id=identifier, project_id=project_id, background=True)
            except Exception:
                self._desktop_requests.pop(identifier, None)
                raise
            return {**self.status(), "job_id": identifier, "job": job}

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
            if result.get("status") in ("error", "failed") and not self.last_error:
                from Backend.core.log_system import redact
                self.last_error = redact(result.get("message") or "操作未成功完成，请查看日志和结果报告")
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

    def _notify_completion(self, name, request, result, *, job=None):
        # Persistence has finished before any completion reaches the desktop.
        payload = {key: value for key, value in result.items() if key != "model"}
        def notify(event, data):
            self.notify(event, data, job=job)
        if name == "translation":
            notify("translation.stopped", payload)
            output = result.get("output")
            output_succeeded = not isinstance(output, dict) or output.get("status") == "success"
            if result.get("status") in ("success", "partial") and not self.last_error and output_succeeded:
                notify("translation.completed", payload)
            if isinstance(output, dict):
                notify("project.export.completed", {"files": [], "report": {}, **output})
        elif name == "analysis":
            notify("analysis.completed", {"analysis_data": None, **payload})
        elif name.startswith("table."):
            notify("table.completed", {
                "file_path": request.get("file_path"), "updated_item_count": 0,
                "operation": name.split(".", 1)[1],
                **payload, "view": request.get("view", "basic"),
            })
        elif name == "glossary.translate":
            notify("glossary.completed", {
                "updated_data": None, **payload, "table_id": request.get("table_id"),
                "request_id": request.get("request_id"),
            })
        elif name == "api_test":
            failure = [result.get("message") or "接口测试未完成"] if result.get("status") in ("error", "failed", "cancelled") else []
            notify("api_test.completed", {"success": [], "failure": failure, **payload})
        elif name == "project.export":
            notify("project.export.completed", {"files": [], "report": {}, **payload})

    def close(self):
        with self.lock:
            self.closing = True
        if self._scheduler is not None:
            self._scheduler.close()
        if not self._started:
            return
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
