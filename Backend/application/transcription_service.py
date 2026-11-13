"""Transcribe audio assets into an operation-owned intermediate model."""
import uuid
from concurrent.futures import ThreadPoolExecutor

from Backend.application.media_workers import copy_file, isolated_file_project, run_file_workers
from pathlib import Path

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.transcription_config import resolve_transcription_config
from Backend.domain.models.cache_item import CacheItem, TranslationStatus
from Backend.domain.models.intermediate import parse_model
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.transcription.provider import SUPPORTED_FORMATS, request_transcription
from Backend.infrastructure.transcription.volcengine import FAST_FORMATS, FAST_MAX_BYTES
from Backend.infrastructure.transcription import deepseek, minimax, openai


def _audio_source(cache_file, reference=None, metadata=None, *, allow_conversion=False):
    metadata = cache_file.media_metadata if metadata is None else metadata
    duration = metadata.get("duration_ms")
    if type(duration) is not int or duration <= 0:
        raise PipelineError("ASR_INVALID_AUDIO", "音频缺少有效时长，请重新读取文件", 400)
    audio_format = metadata.get("format")
    if not isinstance(audio_format, str) or not audio_format or (not allow_conversion and audio_format.lower() not in SUPPORTED_FORMATS):
        raise PipelineError("ASR_INVALID_AUDIO", "音频格式不受当前转录接口支持", 400)
    sample_rate = metadata.get("sample_rate")
    if type(sample_rate) is not int or sample_rate <= 0:
        raise PipelineError("ASR_INVALID_AUDIO", "音频缺少有效采样率，请重新读取文件", 400)
    reference = cache_file.source_ref if reference is None else reference
    if not reference.get("verified") or not reference.get("path") or not reference.get("sha256"):
        raise PipelineError("ASR_SOURCE_UNVERIFIED", "转录需要已校验的本地音频引用，请先读取音频", 400)
    path = Path(reference["path"])
    try:
        if not path.is_file():
            raise PipelineError("ASR_SOURCE_NOT_FOUND", "音频原文件不存在", 400)
        size = path.stat().st_size
        if duration <= 300000 and size > 2 * 1024 ** 3:
            raise PipelineError("ASR_AUDIO_TOO_LARGE", "音频超过接口支持的 2 GB 上限", 400)
        if not size:
            raise PipelineError("ASR_INVALID_AUDIO", "音频原文件为空", 400)
        digest = file_sha256(path)
    except OSError:
        raise PipelineError("ASR_SOURCE_NOT_FOUND", "无法读取音频原文件", 400) from None
    if digest.lower() != reference["sha256"].lower():
        raise PipelineError("ASR_SOURCE_CHANGED", "音频原文件已变化，请重新读取", 409)
    return path, audio_format.lower(), sample_rate, duration


def transcribe_model(model, config=None, context=None) -> dict:
    """Coordinate isolated files and share one request pool across all slices."""
    project = parse_model(model)
    context = context or ExecutionContext()
    files = [file for file in project.files.values() if file.media_type in ("audio", "video")]
    if not files:
        raise PipelineError("ASR_NO_AUDIO", "中间模型中没有音频文件", 400)
    configs = {kind: resolve_transcription_config(config, kind=kind) for kind in {f.media_type for f in files}}
    workers = next(iter(configs.values())).user_thread_counts
    report = {
        "total": len(files), "succeeded": 0, "skipped": 0, "failed": 0,
        "cancelled": False, "cancelled_files": 0, "segment_count": 0,
        "files": [], "errors": [], "warnings": [], "operation_errors": [],
        "usage": {"requests": 0, "duration": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    results = {}
    next_index = max((item.text_index for item in project.items_iter()), default=-1) + 1

    def callback_failed():
        if not report["operation_errors"]:
            report["operation_errors"].append({"code": "ASR_CALLBACK_FAILED", "message": "无法保存转录进度"})
        context.cancel()

    if context.on_model_prepared:
        try:
            context.on_model_prepared(project)
        except Exception:
            callback_failed()
            return {"status": "failed", "model": project, "report": report}

    def event(index, payload):
        file, progress = payload
        project.files[file.storage_path] = file
        if context.on_progress:
            context.on_progress(progress)

    def completed(index, result):
        nonlocal next_index
        results[index] = result["report"]
        local = result["report"]
        file = next(iter(result["model"].files.values()))
        if local["succeeded"]:
            old_indices = [item.text_index for item in files[index].items]
            for ordinal, item in enumerate(file.items):
                if ordinal < len(old_indices):
                    item.text_index = old_indices[ordinal]
                else:
                    item.text_index = next_index
                    next_index += 1
            file.__dict__.pop("items_index_dict", None)
            project.stats_data = None
        project.files[file.storage_path] = file
        for key in ("succeeded", "skipped", "failed", "cancelled_files", "segment_count"):
            report[key] += local[key]
        for key in report["usage"]:
            report["usage"][key] += local["usage"].get(key, 0)
        report["operation_errors"].extend(local["operation_errors"])
        if local["operation_errors"]:
            context.cancel()
        try:
            if context.on_progress:
                context.on_progress({"operation": "transcription", "current": len(results), "total": len(files),
                                     "succeeded": report["succeeded"], "failed": report["failed"],
                                     "skipped": report["skipped"]})
        except Exception:
            callback_failed()

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="asr-request") as requests:
        def work(index, file, emit):
            local = isolated_file_project(project, file)

            def progress(value):
                # Slice and video-preparation checkpoints reach the project
                # before persistence. Terminal progress is owned by completed().
                emit((copy_file(local.files[file.storage_path]), value))

            child = ExecutionContext(source=context.source, cancel_event=context.cancel_event, on_progress=progress)
            return _transcribe_file(local, configs[file.media_type], child, requests)

        try:
            run_file_workers(files, work, workers=workers, context=context,
                             on_event=event, on_result=completed, prefix="asr-file")
        except Exception:
            callback_failed()
    for index in sorted(results):
        for key in ("files", "errors", "warnings"):
            report[key].extend(results[index][key])
    report["cancelled_files"] += len(files) - len(results)
    if not context.is_cancelled() and not report["operation_errors"]:
        from Backend.application.read_service import ensure_media_language_metadata
        try:
            ensure_media_language_metadata(project, media_types=("audio", "video"))
        except PipelineError as error:
            report["operation_errors"].append({"code": error.code, "message": error.message})
    report["cancelled"] = context.is_cancelled() and not report["operation_errors"]
    if report["operation_errors"]:
        status = "partial" if report["succeeded"] else "failed"
    elif report["cancelled"]:
        status = "cancelled"
    elif report["failed"]:
        status = "partial" if report["succeeded"] or report["skipped"] else "failed"
    else:
        status = "success"
    return {"status": status, "model": project, "report": report}


def _transcribe_file(project, resolved, context, request_executor) -> dict:
    """Preserve other media and commit each complete audio result atomically.

    Long files retain successful slices in a portable checkpoint. Cancelling or
    failing leaves the previous transcript untouched; complete files survive.
    """
    audio_files = [cache_file for cache_file in project.files.values() if cache_file.media_type in ("audio", "video")]
    if not audio_files:
        raise PipelineError("ASR_NO_AUDIO", "中间模型中没有音频文件", 400)
    request_config = resolved.to_request_config()
    next_index = max((item.text_index for item in project.items_iter()), default=-1) + 1
    report = {
        "total": len(audio_files), "succeeded": 0, "skipped": 0, "failed": 0,
        "cancelled": False, "cancelled_files": 0, "segment_count": 0,
        "files": [], "errors": [], "warnings": [], "operation_errors": [],
        "usage": {"requests": 0, "duration": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    changed = False
    if context.on_model_prepared:
        try:
            context.on_model_prepared(project)
        except Exception:
            report["operation_errors"].append({"code": "ASR_CALLBACK_FAILED", "message": "无法保存转录初始模型"})
            return {"status": "failed", "model": project, "report": report}
    for ordinal, cache_file in enumerate(audio_files):
        if context.is_cancelled():
            report["cancelled_files"] = len(audio_files) - ordinal
            break
        identity = {"file_id": cache_file.file_id, "path": cache_file.storage_path}
        request_started = False
        chunk_report = None
        try:
            if cache_file.media_type == "video":
                from Backend.infrastructure.transcription.video_audio import prepare_video_audio, verified_video_source
                # A transcript must never be reused against a modified video.
                verified_video_source(cache_file)
            has_checkpoint = isinstance(cache_file.extra.get("transcription_checkpoint"), dict)
            previous = cache_file.extra.get("transcription", {})
            complete_empty = (isinstance(previous, dict) and previous.get("status") == "complete"
                              and previous.get("source_sha256") == cache_file.source_ref.get("sha256"))
            if not resolved.retranscribe and not has_checkpoint and (
                    complete_empty or any(item.source_text.strip() for item in cache_file.items)):
                report["skipped"] += 1
                report["files"].append({**identity, "status": "skipped", "segment_count": len(cache_file.items)})
            else:
                audio_reference, audio_metadata = cache_file.source_ref, cache_file.media_metadata
                if cache_file.media_type == "video":
                    artifact = prepare_video_audio(project.project_id, cache_file, context)
                    audio_reference, audio_metadata = artifact["source_ref"], artifact["media_metadata"]
                deepseek_asr = resolved.api_format == "DeepSeek"
                path, audio_format, sample_rate, duration_ms = _audio_source(
                    cache_file, audio_reference, audio_metadata, allow_conversion=deepseek_asr)
                if context.is_cancelled():
                    report["cancelled_files"] = len(audio_files) - ordinal
                    break
                if (duration_ms > 300000
                        or deepseek_asr and not deepseek.can_upload(audio_metadata, path.stat().st_size)
                        or resolved.api_format == "VolcengineASRFast" and
                        (audio_format not in FAST_FORMATS or path.stat().st_size > FAST_MAX_BYTES)
                        or resolved.api_format == "MiniMax" and
                        (audio_format not in minimax.SUPPORTED_FORMATS or path.stat().st_size > minimax.MAX_AUDIO_BYTES)
                        or resolved.api_format == "OpenAI" and
                        (audio_format not in openai.SUPPORTED_FORMATS or path.stat().st_size > openai.MAX_AUDIO_BYTES)):
                    from Backend.application.long_transcription_service import transcribe_long_audio
                    outcome = transcribe_long_audio(cache_file, path, resolved, context, request_transcription,
                                                    audio_reference=audio_reference, audio_metadata=audio_metadata,
                                                    executor=request_executor)
                    chunk_report = outcome["report"]
                    for key in report["usage"]:
                        report["usage"][key] += chunk_report["usage"].get(key, 0)
                    report["operation_errors"].extend(chunk_report["operation_errors"])
                    # Validate even an incomplete attempt before returning its
                    # checkpoint; results from a changed source cannot be reused.
                    if file_sha256(path).lower() != audio_reference["sha256"].lower():
                        raise PipelineError("ASR_SOURCE_CHANGED", "转录期间音频原文件发生变化，请重新读取", 409)
                    if outcome["status"] == "cancelled":
                        raise PipelineError("ASR_CANCELLED", "转录已取消", 409)
                    if outcome["status"] != "success":
                        error = next(iter(chunk_report["operation_errors"] or chunk_report["errors"]),
                                     {"code": "ASR_CHUNKS_FAILED", "message": "部分音频分片尚未完成，请使用返回模型继续转录"})
                        raise PipelineError(error["code"], error["message"], 502)
                    result = outcome["result"]
                    duration_ms = result.get("duration_ms", duration_ms)
                else:
                    def request_short():
                        if context.is_cancelled():
                            raise PipelineError("ASR_CANCELLED", "转录已取消", 409, {"attempts": 0})
                        audio_bytes = path.read_bytes()
                        # Drain an issued paid request; still gate every POST/retry.
                        return request_transcription(
                            audio_bytes, audio_format=audio_format, sample_rate=sample_rate,
                            duration_ms=duration_ms, config=request_config,
                            context=ExecutionContext(source=context.source), retry_context=context,
                        )
                    request_started = True
                    result = request_executor.submit(request_short).result()
                    report["usage"]["requests"] += result.get("attempts", 1)
                    for key in ("duration", "input_tokens", "output_tokens", "total_tokens"):
                        report["usage"][key] += result.get("usage", {}).get(key, 0)
                request_started = False
                if chunk_report is None and file_sha256(path).lower() != audio_reference["sha256"].lower():
                    raise PipelineError("ASR_SOURCE_CHANGED", "转录期间音频原文件发生变化，请重新读取", 409)
                if cache_file.media_type == "video":
                    verified_video_source(cache_file)
                old_indices = [item.text_index for item in cache_file.items]
                items = []
                for index, segment in enumerate(result["segments"]):
                    start_ms, end_ms = segment["start_ms"], segment["end_ms"]
                    if type(start_ms) is not int or type(end_ms) is not int or not 0 <= start_ms < end_ms <= duration_ms:
                        raise PipelineError("ASR_INVALID_RESPONSE", "转录时间戳不在有效音频范围内", 502)
                    text_index = old_indices[index] if index < len(old_indices) else next_index
                    if index >= len(old_indices):
                        next_index += 1
                    items.append(CacheItem(
                        item_id=uuid.uuid5(uuid.NAMESPACE_URL, f"ainiee:asr:{cache_file.file_id}:{index}:{start_ms}:{end_ms}").hex,
                        text_index=text_index, source_text=segment["text"], translated_text="",
                        translation_status=TranslationStatus.UNTRANSLATED, model="",
                        locator={"kind": cache_file.media_type, "index": index, "start_ms": start_ms, "end_ms": end_ms,
                                 "speaker_id": segment.get("speaker_id")},
                    ))
                # Only after all segments and the source fingerprint are valid.
                cache_file.items = items
                cache_file.__dict__.pop("items_index_dict", None)
                cache_file.extra.pop("transcription_checkpoint", None)
                if cache_file.media_type == "audio":
                    cache_file.media_metadata["duration_ms"] = duration_ms
                language = result.get("language")
                if (not language and resolved.api_format == "DashScope" and len(resolved.language_hints) == 1
                        and not resolved.speaker_diarization_enabled):
                    language = resolved.language_hints[0]
                cache_file.language_stats = [(language, len(items), 1.0)] if language and items else []
                cache_file.lc_language_stats = []
                cache_file.extra["transcription"] = {
                    "provider_id": resolved.provider_id, "model": resolved.model,
                    "source_sha256": cache_file.source_ref["sha256"], "segment_count": len(items),
                    "status": "complete",
                }
                changed = True
                report["succeeded"] += 1
                report["segment_count"] += len(items)
                report["warnings"].extend({**identity, **warning} for warning in result.get("warnings", []))
                report["files"].append({**identity, "status": "success", "segment_count": len(items),
                                        "request_id": result.get("request_id", ""), "attempts": result.get("attempts", 1),
                                        **({"chunks": chunk_report} if chunk_report is not None else {})})
        except PipelineError as error:
            if error.code == "ASR_SOURCE_CHANGED":
                cache_file.extra.pop("transcription_checkpoint", None)
            if error.code == "ASR_CALLBACK_FAILED" and not report["operation_errors"]:
                report["operation_errors"].append({"code": error.code, "message": "转录进度回调失败"})
                context.cancel()
            if request_started:
                report["usage"]["requests"] += (error.details or {}).get("attempts", 0 if error.code == "ASR_CANCELLED" else 1)
            if error.code == "ASR_CANCELLED":
                context.cancel()
                report["cancelled_files"] = len(audio_files) - ordinal
                report["files"].append({**identity, "status": "cancelled",
                                        **({"chunks": chunk_report} if chunk_report is not None else {})})
                break
            entry = {**identity, "code": error.code, "message": error.message}
            report["errors"].append(entry)
            report["failed"] += 1
            report["files"].append({**entry, "status": "failed",
                                    **({"chunks": chunk_report} if chunk_report is not None else {})})
        except Exception:
            # Provider/transport exception strings may contain credentials or a
            # Data URI; do not copy them into results, model metadata, or logs.
            entry = {**identity, "code": "ASR_INTERNAL_ERROR", "message": "转录处理失败，请检查音频与接口配置"}
            report["errors"].append(entry)
            report["failed"] += 1
            report["files"].append({**entry, "status": "failed",
                                    **({"chunks": chunk_report} if chunk_report is not None else {})})
        if report["operation_errors"]:
            report["cancelled_files"] = len(audio_files) - ordinal - 1
            break
    if changed:
        project.stats_data = None
    report["cancelled"] = context.is_cancelled() and not report["operation_errors"]
    if report["operation_errors"]:
        status = "partial" if report["succeeded"] else "failed"
    elif report["cancelled"]:
        status = "cancelled"
    elif report["failed"]:
        status = "partial" if report["succeeded"] or report["skipped"] else "failed"
    else:
        status = "success"
    return {"status": status, "model": project, "report": report}
