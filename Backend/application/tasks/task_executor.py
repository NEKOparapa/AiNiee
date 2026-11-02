"""Synchronous desktop workflows; Runtime owns admission and background work."""
import concurrent.futures
import threading
from contextlib import contextmanager
from dataclasses import replace

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.application.tasks.analysis_task import AnalysisTask
from Backend.application.tasks.proofread_task import ProofreadTask
from Backend.core.config import ConfigMixin
from Backend.core.log import LogMixin
from Backend.domain.config.task_config import TaskConfig
from Backend.domain.models.cache_project import CacheProject, CacheProjectStatistics


class TaskExecutor(ConfigMixin, LogMixin):
    def __init__(self, cache_manager, file_reader=None, file_writer=None) -> None:
        self.cache_manager = cache_manager
        self.file_reader = file_reader
        self.file_writer = file_writer
        self.config = TaskConfig()
        self._executor_lock = threading.RLock()
        self._active_executor = None
        self._active_context = None
        self.translation_clock_running = False
        self._closed = False

    @contextmanager
    def _using_context(self, context):
        with self._executor_lock:
            if self._closed:
                raise PipelineError("EXECUTOR_CLOSED", "任务执行器已关闭", 503)
            if self._active_context is not None:
                raise PipelineError("BUSY", "已有任务正在执行", 409)
            self._active_context = context
        try:
            yield context
        finally:
            with self._executor_lock:
                if self._active_context is context:
                    self._active_context = None
                    self.translation_clock_running = False

    def _set_active_executor(self, executor: concurrent.futures.ThreadPoolExecutor) -> None:
        with self._executor_lock:
            self._active_executor = executor

    def _clear_active_executor(self, executor: concurrent.futures.ThreadPoolExecutor) -> None:
        with self._executor_lock:
            if self._active_executor is executor:
                self._active_executor = None

    def close(self) -> None:
        """Cancel active work; the owner waits for it before closing shared clients."""
        with self._executor_lock:
            self._closed = True
            context = self._active_context
            executor = self._active_executor
        if context is not None:
            context.cancel()
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def analyze(self, context=None) -> dict:
        context = context or ExecutionContext(source="desktop")
        with self._using_context(context):
            return AnalysisTask(
                self.cache_manager, self._set_active_executor,
                self._clear_active_executor, context=context,
            ).run()

    def proofread(self, data, context=None) -> dict:
        context = context or ExecutionContext(source="desktop")
        with self._using_context(context):
            return ProofreadTask(
                data, self._set_active_executor,
                self._clear_active_executor, context=context,
            ).run()

    def export(self, data=None) -> dict:
        """Write the selected project's files and return its complete output report."""
        from Backend.application.write_service import write_model

        with self._using_context(ExecutionContext(source="desktop")):
            if self.cache_manager.project is None:
                raise PipelineError("NO_PROJECT", "项目数据尚未加载")
            config = TaskConfig.read_snapshot()
            output_path = (data or {}).get("export_path") or config.get("label_output_path")
            languages = self.cache_manager.project.translation_context or {}
            result = write_model(self.cache_manager.project, {
                "output_dir": output_path, "mode": "both", "overwrite": True,
                "translated_suffix": config.get("output_filename_suffix", "_translated"),
                "bilingual_suffix": "_bilingual",
                "bilingual_order": config.get("bilingual_text_order", "translation_first"),
                "keep_original_encoding": config.get("keep_original_encoding", False),
                "source_language": languages.get("source_language") or config.get("source_language", "auto"),
                "target_language": languages.get("target_language") or config.get("target_language", "chinese_simplified"),
            })
            if result["status"] == "success":
                self.info(f"翻译结果已成功保存至 {output_path} 目录。")
            else:
                self.warning("部分或全部文件未能导出，请检查输出报告")
            return result

    def translate(self, continue_status=False, context=None) -> dict:
        """Translate with the existing batch workers, save progress, then export."""
        from Backend.application.translation_service import resolve_translation_config, translate_model
        from Backend.application.write_service import write_model

        caller_context = context or ExecutionContext(source="desktop")
        baseline = {}

        def cumulative_statistics(current):
            merged = dict(current)
            for key in ("total_requests", "error_requests", "token", "total_completion_tokens", "time"):
                merged[key] = merged.get(key, 0) + baseline.get(key, 0)
            # Desktop progress uses this origin for its live clock. Move it back
            # by recorded work time, excluding the pause between separate calls.
            if merged.get("start_time"):
                merged["start_time"] -= max(0, baseline.get("time", 0))
            # The service already counts retained translations in line/total_line.
            return merged

        def prepared(model):
            # Keep worker-owned data separate from cache snapshots and UI edits.
            with self.cache_manager.file_lock:
                self.cache_manager.project = CacheProject.from_dict(model.to_dict())
                self.cache_manager.project.stats_data = CacheProjectStatistics.from_dict(
                    cumulative_statistics(model.stats_data.to_dict())
                )
                self.project_status_data = self.cache_manager.project.stats_data
                self.translation_clock_running = True
            self.cache_manager.save_to_file()
            if caller_context.on_model_prepared:
                caller_context.on_model_prepared(model)

        def completed(items, file_path, statistics):
            with self.cache_manager.file_lock:
                file = self.cache_manager.project.get_file(file_path)
                for item in items:
                    cached = file.get_item(item.text_index)
                    with cached.atomic_scope():
                        cached.translated_text = item.translated_text
                        cached.translation_status = item.translation_status
                        cached.model = item.model
                self.project_status_data = CacheProjectStatistics.from_dict(cumulative_statistics(statistics))
                self.cache_manager.project.stats_data = self.project_status_data
            self.cache_manager.require_save_to_file()
            if caller_context.on_batch_complete:
                caller_context.on_batch_complete(items, file_path, cumulative_statistics(statistics))

        def progress(statistics):
            if caller_context.on_progress:
                caller_context.on_progress({
                    **cumulative_statistics(statistics),
                    "elapsed_running": self.translation_clock_running,
                })

        # replace preserves cancellation and every other callback, without
        # mutating the caller's context.
        service_context = replace(
            caller_context, on_model_prepared=prepared,
            on_batch_complete=completed, on_progress=progress,
        )
        with self._using_context(service_context):
            if self.cache_manager.project is None:
                raise PipelineError("NO_PROJECT", "项目数据尚未加载")
            # The desktop's Start action confirms a fresh translation; Continue
            # retains completed rows and accumulates their statistics.
            self.config = resolve_translation_config({"retranslate": not continue_status})
            previous_statistics = self.cache_manager.project.stats_data
            if continue_status and previous_statistics:
                baseline = previous_statistics.to_dict()
            result = translate_model(self.cache_manager.project, self.config, service_context)
            self.translation_clock_running = False
            statistics = cumulative_statistics(result["model"].stats_data.to_dict())
            result["model"].stats_data = CacheProjectStatistics.from_dict(statistics)
            result["report"]["statistics"] = statistics
            with self.cache_manager.file_lock:
                self.cache_manager.project = result["model"]
                self.project_status_data = result["model"].stats_data
            self.cache_manager.save_to_file()
            if service_context.is_cancelled() or result["report"].get("operation_errors"):
                return result

            output = write_model(result["model"], {
                "output_dir": self.config.label_output_path,
                "mode": "both", "overwrite": True,
                "translated_suffix": self.config.output_filename_suffix,
                "bilingual_suffix": "_bilingual",
                "bilingual_order": self.config.bilingual_text_order,
                "keep_original_encoding": self.config.keep_original_encoding,
            })
            result["output"] = output
            if output["status"] == "failed":
                result["status"] = "failed"
            else:
                if output["status"] == "partial":
                    if result["status"] == "success":
                        result["status"] = "partial"
                    self.warning("部分文件导出失败，请检查输出报告")
            return result
