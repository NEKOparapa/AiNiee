"""Cancellable, sample-accurate audio normalization and overlapping VAD chunks."""
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import time
import wave

from Backend.application.pipeline_common import PipelineError
from Backend.core.media_tools import find_media_tool, missing_media_tool_message
from Backend.infrastructure.transcription.vad import (
    FRAME_SAMPLES, MODEL_SHA256, MODEL_VERSION, SAMPLE_RATE, analyze_wave, check_cancelled,
)


MAX_UPLOAD_DURATION_MS = 300_000
NORMALIZE_TIMEOUT_SECONDS = 1800


@dataclass(frozen=True)
class AudioChunk:
    index: int
    start_ms: int
    end_ms: int
    core_start_ms: int
    core_end_ms: int
    path: Path


@dataclass(frozen=True)
class PreparedAudio:
    duration_ms: int
    sample_rate: int
    chunks: list[AudioChunk]
    speech_intervals: list[dict[str, int]]
    report: dict


def _normalize_audio(source, destination, context):
    check_cancelled(context)
    executable = find_media_tool("ffmpeg")
    if not executable:
        raise PipelineError("FFMPEG_UNAVAILABLE", missing_media_tool_message("ffmpeg"), 503)
    command = [executable, "-hide_banner", "-v", "error", "-nostdin", "-y",
               "-protocol_whitelist", "file,pipe", "-i", str(source), "-map", "0:a:0",
               "-vn", "-sn", "-dn", "-map_metadata", "-1", "-ac", "1", "-ar", str(SAMPLE_RATE),
               "-c:a", "pcm_s16le", "-f", "wav", str(destination)]
    error_path = destination.with_suffix(".log")
    process = None
    try:
        with error_path.open("wb") as errors:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            started = time.monotonic()
            while process.poll() is None:
                check_cancelled(context)
                if time.monotonic() - started > NORMALIZE_TIMEOUT_SECONDS:
                    raise PipelineError("AUDIO_NORMALIZATION_TIMEOUT", "音频规范化超时")
                if context is not None:
                    context.cancel_event.wait(0.1)
                else:
                    time.sleep(0.1)
            check_cancelled(context)
        if process.returncode:
            with error_path.open("rb") as errors:
                errors.seek(max(0, error_path.stat().st_size - 1000))
                detail = errors.read().decode("utf-8", errors="replace").strip()
            raise PipelineError("AUDIO_NORMALIZATION_FAILED", f"ffmpeg 无法解码音频: {detail or '未知错误'}")
    except FileNotFoundError as error:
        raise PipelineError("FFMPEG_UNAVAILABLE", missing_media_tool_message("ffmpeg"), 503) from error
    except OSError as error:
        raise PipelineError("AUDIO_NORMALIZATION_FAILED", f"音频规范化失败: {error}") from error
    finally:
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            finally:
                process.wait()


def _core_plan(duration_ms, speech_intervals, chunk_duration_ms):
    """Prefer a quiet point in the final 12.5% (at most 30 s) of each core."""
    silence = []
    cursor = 0
    for interval in speech_intervals:
        start, end = interval["start_ms"], interval["end_ms"]
        if start > cursor:
            silence.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < duration_ms:
        silence.append((cursor, duration_ms))
    cores, cuts = [], []
    start = 0
    lookback = min(30_000, max(1000, chunk_duration_ms // 8))
    while duration_ms - start > chunk_duration_ms:
        target = start + chunk_duration_ms
        earliest = max(start + 1, target - lookback)
        candidates = []
        for left, right in silence:
            if left > target:
                break
            if right - left < 160 or right < earliest:
                continue
            margin = min(200, (right - left) // 2)
            point = min(target, right - margin)
            if point >= max(earliest, left + margin):
                candidates.append(point)
        boundary = max(candidates) if candidates else target
        cores.append((start, boundary))
        cuts.append({"position_ms": boundary, "kind": "silence" if candidates else "hard"})
        start = boundary
    cores.append((start, duration_ms))
    return cores, cuts


def _write_chunk(stream, destination, start_ms, end_ms, total_samples, context):
    start = start_ms * SAMPLE_RATE // 1000
    end = min(total_samples, end_ms * SAMPLE_RATE // 1000)
    stream.setpos(start)
    remaining = end - start
    with wave.open(str(destination), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        while remaining:
            check_cancelled(context)
            count = min(65_536, remaining)
            data = stream.readframes(count)
            if len(data) != count * 2:
                raise PipelineError("AUDIO_CHUNK_FAILED", "规范化音频数据不完整，无法完整切片")
            output.writeframesraw(data)
            remaining -= count


@contextmanager
def prepare_audio_chunks(path, *, chunk_duration_ms=240000, chunk_overlap_ms=2000,
                         vad_threshold=0.35, context=None):
    """Yield temporary upload WAVs; every sample belongs to a continuous core.

    The paths exist only inside the with block. VAD provides boundary hints and
    never removes silent or low-confidence audio, including all-silence inputs.
    """
    if type(chunk_duration_ms) is not int or not 30_000 <= chunk_duration_ms <= 290_000:
        raise PipelineError("INVALID_CHUNK_CONFIG", "chunk_duration_ms 必须为 30000 至 290000 的整数", 422)
    if type(chunk_overlap_ms) is not int or (chunk_overlap_ms != 0 and not 500 <= chunk_overlap_ms <= 5000):
        raise PipelineError("INVALID_CHUNK_CONFIG", "chunk_overlap_ms 必须为 0 或 500 至 5000 的整数", 422)
    if (isinstance(vad_threshold, bool) or not isinstance(vad_threshold, (int, float))
            or not math.isfinite(vad_threshold) or not 0 < vad_threshold < 1):
        raise PipelineError("INVALID_VAD_CONFIG", "vad_threshold 必须在 0 和 1 之间", 422)
    if chunk_duration_ms + 2 * chunk_overlap_ms > MAX_UPLOAD_DURATION_MS:
        raise PipelineError("INVALID_CHUNK_CONFIG", "含重叠的上传片段不能超过 300 秒", 422)
    check_cancelled(context)
    try:
        source = Path(path).expanduser().resolve(strict=True)
        if not source.is_file():
            raise ValueError("not a file")
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        raise PipelineError("INPUT_NOT_FOUND", "音频源文件不可访问") from error
    with TemporaryDirectory(prefix="ainiee-audio-") as directory:
        temporary = Path(directory)
        normalized = temporary / "normalized.wav"
        _normalize_audio(source, normalized, context)
        detected = analyze_wave(normalized, threshold=vad_threshold, context=context)
        duration_ms = (detected.total_samples * 1000 + SAMPLE_RATE - 1) // SAMPLE_RATE
        cores, cuts = _core_plan(duration_ms, detected.speech_intervals, chunk_duration_ms)
        chunks = []
        try:
            with wave.open(str(normalized), "rb") as stream:
                for index, (core_start, core_end) in enumerate(cores):
                    check_cancelled(context)
                    start, end = max(0, core_start - chunk_overlap_ms), min(duration_ms, core_end + chunk_overlap_ms)
                    if end - start > MAX_UPLOAD_DURATION_MS:
                        raise PipelineError("AUDIO_CHUNK_FAILED", "音频切片超过上传时长上限")
                    destination = temporary / f"chunk-{index:05d}.wav"
                    _write_chunk(stream, destination, start, end, detected.total_samples, context)
                    chunks.append(AudioChunk(index, start, end, core_start, core_end, destination))
        except (OSError, EOFError, wave.Error) as error:
            raise PipelineError("AUDIO_CHUNK_FAILED", f"音频切片失败: {error}") from error
        check_cancelled(context)
        speech_found = bool(detected.speech_intervals)
        report = {
            "duration_ms": duration_ms, "sample_rate": SAMPLE_RATE, "channels": 1, "format": "wav",
            "decoded_duration_ms": duration_ms, "coverage_start_ms": 0, "coverage_end_ms": duration_ms,
            "total_samples": detected.total_samples, "chunk_count": len(chunks),
            "chunk_duration_ms": chunk_duration_ms, "chunk_overlap_ms": chunk_overlap_ms,
            "uploaded_duration_ms": sum(chunk.end_ms - chunk.start_ms for chunk in chunks),
            "vad_detected_speech": speech_found, "vad_model": f"silero-vad-{MODEL_VERSION}",
            "vad_algorithm": "silero-onnx", "speech_interval_count": len(detected.speech_intervals),
            "speech_duration_ms": sum(interval["end_ms"] - interval["start_ms"] for interval in detected.speech_intervals),
            "vad_model_sha256": MODEL_SHA256, "vad_threshold": vad_threshold, "vad_frame_samples": FRAME_SAMPLES,
            "silence_cuts": sum(cut["kind"] == "silence" for cut in cuts),
            "hard_cuts": sum(cut["kind"] == "hard" for cut in cuts),
            "forced_cuts": sum(cut["kind"] == "hard" for cut in cuts), "cuts": cuts,
            "warnings": [] if speech_found else [{"code": "VAD_NO_SPEECH", "message": "未检测到明确语音；仍完整保留全部音频供转录"}],
        }
        yield PreparedAudio(duration_ms, SAMPLE_RATE, chunks, detected.speech_intervals, report)
