"""Translate an operation-owned intermediate model without exporting files."""
import copy
import time
from concurrent.futures import FIRST_COMPLETED, CancelledError, ThreadPoolExecutor, wait
from types import SimpleNamespace

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.application.tasks.translator_task import TranslatorTask
from Backend.domain.config.task_config import TaskConfig
from Backend.domain.config.platform_concurrency import validate_thread_count
from Backend.domain.config.tables import TableConfigHelper
from Backend.domain.languages import get_source_language_for_file, map_language_name_to_code
from Backend.domain.models.cache_item import TranslationStatus
from Backend.domain.models.cache_project import CacheProjectStatistics
from Backend.domain.models.intermediate import generate_item_chunks, parse_model
from Backend.domain.prompts.glossary_helper import GlossaryHelper
from Backend.domain.text.filters.text_filter import TextFilter
from Backend.infrastructure.llm.request_limiter import RequestLimiter


TRANSLATION_OVERRIDE_FIELDS = frozenset({
    "source_language", "target_language", "provider_id", "retranslate",
    "lines_limit", "tokens_limit", "lines_limit_switch", "tokens_limit_switch",
    "pre_line_counts", "round_limit", "request_timeout", "user_thread_counts",
    "language_filter_switch", "code_filter_switch", "few_shot_and_example_switch",
    "auto_process_text_code_segment", "text_symbol_repair_switch", "response_check_switch",
    "translation_prompt_selection", "characterization_switch", "characterization_data",
    "translation_example_switch", "translation_example_data", "world_building_switch",
    "world_building_content", "writing_style_switch", "writing_style_content",
    "prompt_dictionary_tables", "exclusion_list_tables", "pre_translation_tables",
    "post_translation_tables", "prompt_dictionary_switch", "prompt_dictionary_data",
    "exclusion_list_switch", "exclusion_list_data", "pre_translation_switch",
    "pre_translation_data", "post_translation_switch", "post_translation_data",
})


def _apply_legacy_table_overrides(values, overrides):
    """Map explicit legacy rows/switches into operation-local table snapshots.

    Rows replace the category with one temporary table; an omitted switch keeps
    its effective enabled state. A switch alone toggles the copied tables while
    preserving their rows and matching rules. Mixing public representations for
    the same category is rejected instead of silently picking one.
    """
    for kind in TableConfigHelper.KINDS:
        tables_key, data_key, switch_key = f"{kind}_tables", f"{kind}_data", f"{kind}_switch"
        legacy_keys = {data_key, switch_key}.intersection(overrides)
        if not legacy_keys:
            continue
        if tables_key in overrides:
            raise PipelineError("INVALID_TRANSLATION_CONFIG", f"{tables_key} 不能与旧式 data/switch 字段同时提供")
        if switch_key in overrides and not isinstance(overrides[switch_key], bool):
            raise PipelineError("INVALID_TRANSLATION_CONFIG", f"{switch_key} 必须是布尔值")
        if data_key in overrides and (
            not isinstance(overrides[data_key], list)
            or any(not isinstance(row, dict) for row in overrides[data_key])
        ):
            raise PipelineError("INVALID_TRANSLATION_CONFIG", f"{data_key} 必须是对象数组")
        tables = TableConfigHelper.get_tables(values, kind)
        if data_key in overrides:
            enabled = overrides.get(switch_key, TableConfigHelper.has_enabled_tables(values, kind))
            template = next((table for table in tables if table["enabled"]), tables[0] if tables else {})
            tables = [TableConfigHelper.new_table(
                kind, "本次调用", rows=overrides[data_key], enabled=enabled,
                match_options=template.get("match_options"),
            )]
        else:
            if not tables:
                tables = [TableConfigHelper.new_table(kind, "本次调用", rows=[])]
            for table in tables:
                table["enabled"] = overrides[switch_key]
        values[tables_key] = tables


def resolve_translation_config(config=None) -> TaskConfig:
    """Read defaults once, then resolve a private, non-persisting snapshot."""
    thread_count_override = None
    if isinstance(config, TaskConfig):
        values = copy.deepcopy(getattr(config, "_source_snapshot", config.get_vars()))
        # Runtime changes on a prepared object (e.g. an explicit language) win.
        values.update({key: copy.deepcopy(value) for key, value in config.get_vars().items()
                       if key in TRANSLATION_OVERRIDE_FIELDS and key not in ("provider_id", "user_thread_counts")})
        if getattr(config, "prepared_interface_role", None) == "translate":
            # Preserve the resolved worker count; do not probe a local model's
            # slots endpoint a second time for the desktop's prepared snapshot.
            thread_count_override = config.actual_thread_counts
        # Legacy configurations historically selected the mode by this flag.
        values["lines_limit_switch"] = not values.get("tokens_limit_switch", True)
        provider_id = getattr(config, "target_platform", None)
    else:
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise PipelineError("INVALID_TRANSLATION_CONFIG", "config 必须是对象")
        unknown = set(config) - TRANSLATION_OVERRIDE_FIELDS
        if unknown:
            raise PipelineError("INVALID_TRANSLATION_CONFIG", "不支持的翻译配置字段", details={"fields": sorted(unknown)})
        if "user_thread_counts" in config:
            try:
                thread_count_override = validate_thread_count(config["user_thread_counts"])
            except ValueError as error:
                raise PipelineError("INVALID_TRANSLATION_CONFIG", str(error)) from error
        try:
            values = TaskConfig.read_snapshot()
        except (OSError, ValueError) as error:
            raise PipelineError("INVALID_TRANSLATION_CONFIG", "后端配置无法读取") from error
        _apply_legacy_table_overrides(values, config)
        values["lines_limit_switch"] = not values.get("tokens_limit_switch", True)
        values.update(copy.deepcopy(config))
        # Either public switch can select the mode on its own. Never let a
        # default from the other mode silently override the explicit choice.
        if "lines_limit_switch" in config and "tokens_limit_switch" not in config:
            values["tokens_limit_switch"] = not config["lines_limit_switch"]
        elif "tokens_limit_switch" in config and "lines_limit_switch" not in config:
            values["lines_limit_switch"] = not config["tokens_limit_switch"]
        provider_id = values.pop("provider_id", None)

    for name, low, high in (
        ("lines_limit", 1, 9999999), ("tokens_limit", 1, 9999999),
        ("pre_line_counts", 0, 9999999), ("round_limit", 0, 9999999),
    ):
        value = values.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise PipelineError("INVALID_TRANSLATION_CONFIG", f"{name} 必须是 {low} 至 {high} 的整数")
    timeout = values.get("request_timeout")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 9999999:
        raise PipelineError("INVALID_TRANSLATION_CONFIG", "request_timeout 必须大于 0 且不超过 9999999 秒")
    for name in ("retranslate", "tokens_limit_switch", "lines_limit_switch"):
        if name in values and not isinstance(values[name], bool):
            raise PipelineError("INVALID_TRANSLATION_CONFIG", f"{name} 必须是布尔值")
    if values["tokens_limit_switch"] == values["lines_limit_switch"]:
        raise PipelineError("INVALID_TRANSLATION_CONFIG", "行数模式与 token 模式必须且只能启用一个")
    if provider_id is not None and (not isinstance(provider_id, str) or not provider_id.strip()):
        raise PipelineError("INVALID_TRANSLATION_CONFIG", "provider_id 必须是非空字符串")
    for name in ("source_language", "target_language"):
        value = values.get(name)
        if not isinstance(value, str) or not value.strip() or (name == "target_language" and value == "auto"):
            raise PipelineError("INVALID_TRANSLATION_CONFIG", f"{name} 无效")
        if value != "auto":
            try:
                import langcodes
                if not langcodes.tag_is_valid(map_language_name_to_code(value)):
                    raise ValueError("unknown language")
            except (ValueError, LookupError) as error:
                raise PipelineError("INVALID_TRANSLATION_CONFIG", f"{name} 无效") from error
    try:
        resolved = TaskConfig.from_snapshot(values, "translate", provider_id=provider_id,
                                            user_thread_counts=thread_count_override)
        if isinstance(config, TaskConfig) and getattr(config, "prepared_interface_role", None) == "translate":
            resolved.copy_prepared_concurrency(config)
        if not resolved.model:
            raise ValueError("所选接口未设置模型")
        if isinstance(resolved.rpm_limit, bool) or not isinstance(resolved.rpm_limit, (int, float)) or resolved.rpm_limit <= 0:
            raise ValueError("接口 RPM 必须大于 0")
        return resolved
    except (ValueError, TypeError, AttributeError) as error:
        raise PipelineError("INVALID_TRANSLATION_CONFIG", str(error)) from error


def translate_model(model, config=None, context=None) -> dict:
    """One top-level call; batches may run concurrently within its thread pool.

    Callbacks run on the coordinating thread, after a batch has finished. The
    caller owns admission control; this function never touches Runtime's cache.
    """
    project = parse_model(model)
    if project.project_type == "Image" or any(file.media_type == "image" for file in project.files.values()):
        raise PipelineError("IMAGE_GENERATION_REQUIRED", "图片翻译仅支持单步生图接口", 422)
    resolved = resolve_translation_config(config)
    context = context or ExecutionContext()
    previous_target = (project.translation_context or {}).get("target_language")
    retranslate = bool(getattr(resolved, "retranslate", False))
    if previous_target and previous_target != resolved.target_language and not retranslate:
        raise PipelineError("TARGET_LANGUAGE_CONFLICT", "目标语言发生变化，请显式设置 retranslate=true 全量重译")

    if resolved.source_language == "auto" or getattr(resolved, "language_filter_switch", True):
        from Backend.application.read_service import ensure_media_language_metadata
        ensure_media_language_metadata(project)

    all_items = list(project.items_iter())
    valid_statuses = (TranslationStatus.TRANSLATED, TranslationStatus.POLISHED)
    for item in all_items:
        if retranslate:
            item.translated_text = ""
            item.model = ""
            if item.translation_status != TranslationStatus.EXCLUDED:
                item.translation_status = TranslationStatus.UNTRANSLATED
        elif item.translation_status in valid_statuses and not item.translated_text:
            item.translation_status = TranslationStatus.UNTRANSLATED
    project.translation_context = {
        **(project.translation_context or {}),
        "source_language": resolved.source_language,
        "target_language": resolved.target_language,
    }
    # These rows are data from this model, not from Runtime's selected project.
    analysis_data = project.get_extra("analysis_v1", {}) or {}
    resolved.load_project_table_data(SimpleNamespace(get_analysis_data=lambda: analysis_data))
    preserved = {item.item_id: item.translation_status for item in all_items
                 if item.translation_status in valid_statuses and item.translated_text}
    TextFilter().filter_project(resolved, project)
    for item in all_items:
        if item.item_id in preserved:
            item.translation_status = preserved[item.item_id]
    candidates = [item for item in all_items if item.translation_status == TranslationStatus.UNTRANSLATED]
    for item in candidates:
        item.translated_text = ""
        item.model = ""

    statistics = CacheProjectStatistics(total_line=len(candidates) + len(preserved), line=len(preserved))
    project.stats_data = statistics
    limiter = RequestLimiter()
    limiter.set_limit(resolved.rpm_limit)
    failures = {}
    completed_ids = set()
    operation_errors = []
    stage = "model_prepared_callback"

    def abort_operation(error):
        from Backend.core.log_system import redact
        operation_errors.append({"code": "OPERATION_FAILED", "stage": stage, "message": redact(str(error))})
        context.cancel()

    def consume_result(future, items, file_path, *, notify=True):
        nonlocal stage
        try:
            result = future.result() or {}
        except CancelledError:
            return
        except Exception as error:
            from Backend.core.log_system import redact
            result = {"check_result": False, "error": redact(str(error))}
        if not isinstance(result, dict):
            result = {"check_result": False, "error": "翻译批次返回结构无效"}
        if result.get("cancelled"):
            return
        statistics.total_requests += 1
        statistics.error_requests += 0 if result.get("check_result") else 1
        prompt_tokens = result.get("prompt_tokens", 0) or 0
        completion_tokens = result.get("completion_tokens", 0) or 0
        statistics.token += prompt_tokens + completion_tokens
        statistics.total_completion_tokens += completion_tokens
        statistics.time = time.time() - statistics.start_time
        for item in items:
            if item.translation_status in valid_statuses:
                failures.pop(item.item_id, None)
                completed_ids.add(item.item_id)
            else:
                failures[item.item_id] = (result.get("item_errors") or {}).get(item.item_id) or result.get("error") or "译文未通过检查"
        statistics.line = len(preserved) + len(completed_ids)
        snapshot = statistics.to_dict()
        if notify and context.on_batch_complete:
            stage = "batch_complete_callback"
            context.on_batch_complete(items, file_path, snapshot)
        if notify and context.on_progress:
            stage = "progress_callback"
            context.on_progress(snapshot)

    try:
        if context.on_model_prepared:
            context.on_model_prepared(project)
        if context.on_progress:
            stage = "progress_callback"
            context.on_progress(statistics.to_dict())
        for round_index in range(resolved.round_limit):
            if context.is_cancelled():
                break
            if not any(item.translation_status == TranslationStatus.UNTRANSLATED for item in candidates):
                break
            if round_index:
                resolved.lines_limit = max(1, resolved.lines_limit // 2)
                resolved.tokens_limit = max(1, resolved.tokens_limit // 2)
            stage = "batching"
            chunks, previous, file_paths = generate_item_chunks(
                project, "token" if resolved.tokens_limit_switch else "line",
                resolved.tokens_limit if resolved.tokens_limit_switch else resolved.lines_limit,
                resolved.pre_line_counts,
            )
            tasks = []
            stage = "batch_preparation"
            for items, earlier, file_path in zip(chunks, previous, file_paths):
                if context.is_cancelled():
                    break
                source_language = get_source_language_for_file(
                    resolved.source_language, resolved.target_language, project.get_file(file_path).language_stats,
                )
                task = TranslatorTask(resolved, limiter, source_language, context=context)
                task.set_items(items)
                task.set_previous_items(earlier)
                task.prepare(resolved.target_platform)
                tasks.append((task, items, file_path))
            GlossaryHelper.clear_cache()
            stage = "batch_execution"
            executor = ThreadPoolExecutor(max_workers=max(1, min(resolved.worker_thread_counts, len(tasks))), thread_name_prefix="translator")
            pending = {}
            try:
                for task, items, file_path in tasks:
                    if context.is_cancelled():
                        break
                    pending[executor.submit(task.start)] = (items, file_path)
                while pending:
                    if context.is_cancelled():
                        for future in pending:
                            future.cancel()
                    completed, _ = wait(tuple(pending), timeout=0.1, return_when=FIRST_COMPLETED)
                    for future in completed:
                        items, file_path = pending.pop(future)
                        stage = "batch_result"
                        consume_result(future, items, file_path)
            except Exception as error:
                # Stop queued requests before shutdown starts waiting. In-flight
                # replies are still collected below, without invoking a failed
                # observer again or discarding its completed translations.
                abort_operation(error)
                for future in pending:
                    future.cancel()
            finally:
                executor.shutdown(wait=True, cancel_futures=context.is_cancelled())
                for future, (items, file_path) in pending.items():
                    consume_result(future, items, file_path, notify=False)
    except Exception as error:
        abort_operation(error)

    successful = [item.item_id for item in candidates if item.translation_status in valid_statuses]
    remaining = [item for item in candidates if item.translation_status not in valid_statuses]
    statistics.time = time.time() - statistics.start_time
    statistics.line = len(preserved) + len(successful)
    user_cancelled = context.is_cancelled() and not operation_errors
    report = {
        "total": len(all_items), "succeeded": len(successful),
        "skipped": len(all_items) - len(candidates), "failed": len(remaining),
        "cancelled": user_cancelled, "succeeded_item_ids": successful,
        "operation_errors": operation_errors,
        "failed_items": [{"item_id": item.item_id,
                          "code": "CANCELLED" if user_cancelled else ("OPERATION_ABORTED" if operation_errors else "TRANSLATION_FAILED"),
                          "message": failures.get(item.item_id, "操作已取消" if user_cancelled else ("操作异常中止" if operation_errors else "未获得有效译文"))}
                         for item in remaining],
        "usage": {"prompt_tokens": statistics.token - statistics.total_completion_tokens,
                  "completion_tokens": statistics.total_completion_tokens,
                  "requests": statistics.total_requests},
        "statistics": statistics.to_dict(),
    }
    if operation_errors:
        status = "partial" if successful or preserved else "failed"
    elif user_cancelled:
        status = "cancelled"
    else:
        status = "success" if not remaining else ("partial" if successful or preserved else "failed")
    return {"status": status, "model": project, "report": report}
