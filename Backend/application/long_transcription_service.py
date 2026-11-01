"""Bounded long-audio requests with portable, credential-free checkpoints."""
import copy
import math
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.transcription.audio_chunks import prepare_audio_chunks
from Backend.infrastructure.transcription.chunk_merge import merge_chunk_results


CHECKPOINT_KEY = "transcription_checkpoint"
USAGE_KEYS = ("duration", "input_tokens", "output_tokens", "total_tokens")


def empty_usage():
    return {"requests": 0, **dict.fromkeys(USAGE_KEYS, 0)}


def _usage(value):
    value = value if isinstance(value, dict) else {}
    return {key: number for key in USAGE_KEYS
            if isinstance((number := value.get(key)), (int, float))
            and not isinstance(number, bool) and math.isfinite(number) and number >= 0}


def _attempts(value, default=1):
    return value if type(value) is int and value >= 0 else default


def _safe_result(result, duration_ms):
    """Persist only the provider's text/timing, never its request or raw payload."""
    if not isinstance(result, dict) or not isinstance(result.get("segments"), list):
        raise PipelineError("ASR_INVALID_CHUNK_RESULT", "分片转录结果格式无效", 502)
    segments = []
    for segment in result["segments"]:
        if not isinstance(segment, dict):
            raise PipelineError("ASR_INVALID_CHUNK_RESULT", "分片转录结果格式无效", 502)
        start, end, text = segment.get("start_ms"), segment.get("end_ms"), segment.get("text")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration_ms or not isinstance(text, str):
            raise PipelineError("ASR_INVALID_CHUNK_RESULT", "分片转录时间戳或文本无效", 502)
        speaker = segment.get("speaker_id")
        cleaned = {"text": text, "start_ms": start, "end_ms": end,
                   "speaker_id": str(speaker) if isinstance(speaker, (str, int)) else None}
        if "words" in segment:
            words = segment["words"]
            if not isinstance(words, list):
                raise PipelineError("ASR_INVALID_CHUNK_RESULT", "分片词级时间戳无效", 502)
            cleaned["words"] = []
            for word in words:
                if not isinstance(word, dict):
                    raise PipelineError("ASR_INVALID_CHUNK_RESULT", "分片词级时间戳无效", 502)
                begin, finish = word.get("start_ms"), word.get("end_ms")
                if (type(begin) is not int or type(finish) is not int
                        or not start <= begin < finish <= end or not isinstance(word.get("text"), str)):
                    raise PipelineError("ASR_INVALID_CHUNK_RESULT", "分片词级时间戳无效", 502)
                cleaned["words"].append({"text": word["text"], "start_ms": begin, "end_ms": finish})
        segments.append(cleaned)
    text = result.get("text", "".join(segment["text"] for segment in segments))
    if not isinstance(text, str):
        raise PipelineError("ASR_INVALID_CHUNK_RESULT", "分片转录文本无效", 502)
    language = result.get("language")
    return {"text": text, "segments": segments,
            "language": language if isinstance(language, str) else None,
            "usage": _usage(result.get("usage")), "attempts": _attempts(result.get("attempts")),
            "warnings": [{"code": warning["code"], "message": warning["message"]}
                         for warning in result.get("warnings", [])
                         if isinstance(warning, dict) and isinstance(warning.get("code"), str)
                         and isinstance(warning.get("message"), str)]}


def _checkpoint(cache_file, prepared, resolved):
    plan = [{key: getattr(chunk, key) for key in
             ("index", "start_ms", "end_ms", "core_start_ms", "core_end_ms")} for chunk in prepared.chunks]
    identity = {
        "source_sha256": cache_file.source_ref["sha256"].lower(),
        "endpoint": resolved.api_url, "model": resolved.model, "api_format": resolved.api_format,
        "language_hints": list(resolved.language_hints),
        "speaker_diarization_enabled": resolved.speaker_diarization_enabled,
        "keep_dialect": resolved.keep_dialect,
        "chunk_duration_ms": round(resolved.chunk_duration_seconds * 1000),
        "chunk_overlap_ms": round(resolved.chunk_overlap_seconds * 1000),
        "vad_threshold": resolved.vad_threshold,
        "duration_ms": prepared.duration_ms, "sample_rate": prepared.sample_rate,
    }
    previous = cache_file.extra.get(CHECKPOINT_KEY)
    completed = {}
    reusable = (not resolved.retranscribe and isinstance(previous, dict)
                and previous.get("schema_version") == 1 and previous.get("identity") == identity
                and previous.get("plan") == plan and isinstance(previous.get("completed"), dict))
    if reusable:
        for chunk in prepared.chunks:
            value = previous["completed"].get(str(chunk.index))
            if value is not None:
                try:
                    completed[str(chunk.index)] = _safe_result(value, chunk.end_ms - chunk.start_ms)
                except PipelineError:
                    # A malformed/imported checkpoint must not skip a paid chunk.
                    continue
    checkpoint = {"schema_version": 1, "status": "incomplete", "identity": identity,
                  "plan": plan, "completed": completed}
    cache_file.extra[CHECKPOINT_KEY] = checkpoint
    return checkpoint


def transcribe_long_audio(cache_file, path, resolved, context, requester):
    """Keep completed chunks on the operation's model, even after cancellation."""
    report = {"total": 0, "cached_chunks": 0, "succeeded": 0, "failed": 0, "cancelled_chunks": 0,
              "chunks": [], "errors": [], "warnings": [], "operation_errors": [], "usage": empty_usage()}
    with prepare_audio_chunks(
        path, chunk_duration_ms=round(resolved.chunk_duration_seconds * 1000),
        chunk_overlap_ms=round(resolved.chunk_overlap_seconds * 1000),
        vad_threshold=resolved.vad_threshold, context=context,
    ) as prepared:
        if prepared.duration_ms != cache_file.media_metadata["duration_ms"]:
            # Container duration estimates may drift, especially with VBR audio.
            # The decoded sample count is authoritative once the source matches.
            report["warnings"].append({"code": "ASR_DURATION_CORRECTED", "message": "已按完整解码后的样本数量校正音频时长"})
        if file_sha256(path).lower() != cache_file.source_ref["sha256"].lower():
            cache_file.extra.pop(CHECKPOINT_KEY, None)
            raise PipelineError("ASR_SOURCE_CHANGED", "准备分片期间音频原文件发生变化，请重新读取", 409)
        if not prepared.chunks:
            raise PipelineError("ASR_INVALID_AUDIO", "音频切片结果为空", 400)
        checkpoint = _checkpoint(cache_file, prepared, resolved)
        completed = checkpoint["completed"]
        report["total"] = len(prepared.chunks)
        # This is the chunker's documented JSON report, never its temporary paths.
        preparation_keys = {
            "duration_ms", "decoded_duration_ms", "sample_rate", "channels", "format", "total_samples",
            "chunk_count", "chunk_duration_ms", "chunk_overlap_ms", "uploaded_duration_ms",
            "vad_detected_speech", "vad_model", "vad_model_sha256", "vad_threshold", "vad_frame_samples",
            "speech_interval_count", "speech_duration_ms", "hard_cuts", "forced_cuts", "silence_cuts",
            "coverage_start_ms", "coverage_end_ms", "cuts", "warnings",
        }
        report["preparation"] = {key: copy.deepcopy(value) for key, value in prepared.report.items() if key in preparation_keys}
        report["cached_chunks"] = len(completed)
        report["succeeded"] = len(completed)
        report["chunks"].extend({"index": chunk.index, "start_ms": chunk.start_ms, "end_ms": chunk.end_ms,
                                 "status": "cached", "attempts": 0}
                                for chunk in prepared.chunks if str(chunk.index) in completed)
        missing = iter(chunk for chunk in prepared.chunks if str(chunk.index) not in completed)
        request_config = resolved.to_request_config()

        def request(chunk):
            if context.is_cancelled():
                raise PipelineError("ASR_CANCELLED", "转录已取消", 409, {"attempts": 0})
            # Only bounded, decoded slices are read into memory; never the long
            # original asset. The context manager retains slices until workers join.
            try:
                audio = Path(chunk.path).read_bytes()
            except OSError:
                raise PipelineError("ASR_CHUNK_READ_FAILED", "无法读取准备好的音频分片，请重试", 500, {"attempts": 0}) from None
            if context.is_cancelled():
                raise PipelineError("ASR_CANCELLED", "转录已取消", 409, {"attempts": 0})
            # Once sent, finish receiving this paid request even if the parent
            # cancels. The parent still gates every first POST and retry.
            request_context = ExecutionContext(source=context.source)
            return requester(audio, audio_format="wav", sample_rate=prepared.sample_rate,
                             duration_ms=chunk.end_ms - chunk.start_ms,
                             config=request_config, context=request_context, retry_context=context)

        pending = {}
        with ThreadPoolExecutor(max_workers=resolved.chunk_concurrency, thread_name_prefix="asr-chunk") as executor:
            def submit_available():
                while len(pending) < resolved.chunk_concurrency and not context.is_cancelled():
                    chunk = next(missing, None)
                    if chunk is None:
                        break
                    pending[executor.submit(request, chunk)] = chunk

            submit_available()
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda item: pending[item].index):
                    chunk = pending.pop(future)
                    entry = {"index": chunk.index, "start_ms": chunk.start_ms, "end_ms": chunk.end_ms}
                    attempts = 0
                    try:
                        raw = future.result()
                        attempts = _attempts(raw.get("attempts")) if isinstance(raw, dict) else 1
                        report["usage"]["requests"] += attempts
                        for key, value in _usage(raw.get("usage") if isinstance(raw, dict) else {}).items():
                            report["usage"][key] += value
                        result = _safe_result(raw, chunk.end_ms - chunk.start_ms)
                        completed[str(chunk.index)] = result
                        report["succeeded"] += 1
                        entry.update(status="success", attempts=attempts, usage=result["usage"])
                    except PipelineError as error:
                        if attempts == 0:
                            attempts = _attempts((error.details or {}).get("attempts"), 0 if error.code == "ASR_CANCELLED" else 1)
                            report["usage"]["requests"] += attempts
                        entry.update(status="cancelled" if error.code == "ASR_CANCELLED" else "failed",
                                     code=error.code, message=error.message, attempts=attempts)
                        if error.code == "ASR_CANCELLED":
                            context.cancel()
                            report["cancelled_chunks"] += 1
                        else:
                            report["failed"] += 1
                            report["errors"].append({**entry})
                    except Exception:
                        if attempts == 0:
                            report["usage"]["requests"] += 1
                        entry.update(status="failed", code="ASR_INTERNAL_ERROR", message="分片转录处理失败，请重试", attempts=attempts or 1)
                        report["failed"] += 1
                        report["errors"].append({**entry})
                    report["chunks"].append(entry)
                    if context.on_progress and not report["operation_errors"]:
                        try:
                            context.on_progress({"operation": "transcription", "stage": "transcription", "phase": "chunks",
                                                 "file_id": cache_file.file_id, "path": cache_file.storage_path,
                                                 "chunk_index": chunk.index, "chunk_status": entry["status"],
                                                 "completed_chunks": len(completed), "total_chunks": len(prepared.chunks),
                                                 "cached_chunks": report["cached_chunks"], "failed_chunks": report["failed"],
                                                 "usage": copy.deepcopy(report["usage"])})
                        except Exception:
                            report["operation_errors"].append({"code": "ASR_CALLBACK_FAILED", "message": "转录进度回调失败"})
                            context.cancel()
                submit_available()

        report["pending_chunks"] = len(prepared.chunks) - len(completed) - report["failed"] - report["cancelled_chunks"]
        report["chunks"].sort(key=lambda entry: entry["index"])
        if report["operation_errors"]:
            return {"status": "failed", "report": report}
        if context.is_cancelled():
            return {"status": "cancelled", "report": report}
        if len(completed) != len(prepared.chunks):
            return {"status": "failed", "report": report}
        try:
            result = merge_chunk_results(prepared.chunks, {int(key): value for key, value in completed.items()},
                                         duration_ms=prepared.duration_ms)
        except PipelineError as error:
            report["errors"].append({"code": error.code, "message": error.message})
            return {"status": "failed", "report": report}
        except Exception:
            report["errors"].append({"code": "ASR_INVALID_CHUNK_RESULT", "message": "转录分片合并失败，请检查返回结果"})
            return {"status": "failed", "report": report}
        result["warnings"] = report["warnings"] + prepared.report.get("warnings", []) + result.get("warnings", [])
        languages = {value.get("language") for value in completed.values() if value.get("language")}
        result["language"] = next(iter(languages)) if len(languages) == 1 else None
        result["attempts"] = report["usage"]["requests"]
        result["duration_ms"] = prepared.duration_ms
        result["usage"] = {key: report["usage"][key] for key in USAGE_KEYS}
        report["merge"] = result.get("report", {})
        return {"status": "success", "result": result, "report": report}
