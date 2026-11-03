"""Owned, cancellable video derivatives. Never send a video container to ASR."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import NamedTemporaryFile
import time

from Backend.application.pipeline_common import PipelineError
from Backend.core.media_tools import find_media_tool, missing_media_tool_message
from Backend.core.paths import project_cache_root
from Backend.infrastructure.files.audio_probe import probe_audio
from Backend.infrastructure.files.pipeline_support import file_sha256
from Backend.infrastructure.files.video_probe import probe_video


EXTRACTION_VERSION = 1
SAMPLE_RATE = 16000
PROCESS_TIMEOUT_SECONDS = 1800
_ID = re.compile(r"[A-Za-z0-9_-]+\Z")


def video_cache_root():
    return (project_cache_root() / "VideoAudio").resolve()


def video_cache_directory(project_id, file_id):
    if not all(isinstance(value, str) and _ID.fullmatch(value) for value in (project_id, file_id)):
        raise PipelineError("VIDEO_INVALID_CACHE", "视频项目或文件标识无效", 422)
    root = video_cache_root()
    path = root / project_id / file_id
    if path.resolve() != path or not path.is_relative_to(root):
        raise PipelineError("VIDEO_INVALID_CACHE", "视频缓存路径无效", 422)
    return path


def _cancelled(context):
    if context is not None and context.is_cancelled():
        raise PipelineError("ASR_CANCELLED", "视频音轨处理已取消", 409)


def _progress(context, **values):
    if context is not None and context.on_progress:
        try:
            context.on_progress(values)
        except Exception as error:
            context.cancel()
            raise PipelineError("ASR_CALLBACK_FAILED", "无法保存视频处理进度", 500) from error


def _run_ffmpeg(arguments, destination, context):
    _cancelled(context)
    executable = find_media_tool("ffmpeg")
    if not executable:
        raise PipelineError("FFMPEG_UNAVAILABLE", missing_media_tool_message("ffmpeg"), 503)
    process = None
    try:
        # stderr is bounded by a file, avoiding pipe deadlocks on damaged input.
        with NamedTemporaryFile(dir=destination.parent, suffix=".log") as errors:
            process = subprocess.Popen(
                [executable, "-hide_banner", "-v", "error", "-nostdin", "-y", *arguments, str(destination)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errors,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            started = time.monotonic()
            while process.poll() is None:
                _cancelled(context)
                if time.monotonic() - started > PROCESS_TIMEOUT_SECONDS:
                    raise PipelineError("VIDEO_PROCESS_TIMEOUT", "视频音轨处理超时", 408)
                if context is not None:
                    context.cancel_event.wait(0.1)
                else:
                    time.sleep(0.1)
            _cancelled(context)
            if process.returncode or not destination.is_file() or not destination.stat().st_size:
                raise PipelineError("VIDEO_PROCESS_FAILED", "无法提取视频音轨，请检查视频编码、文件和缓存空间")
    except FileNotFoundError as error:
        raise PipelineError("FFMPEG_UNAVAILABLE", missing_media_tool_message("ffmpeg"), 503) from error
    except OSError as error:
        raise PipelineError("VIDEO_PROCESS_FAILED", "视频处理失败，请检查文件权限和缓存空间") from error
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()


def verified_video_source(cache_file):
    reference = cache_file.source_ref
    if not reference.get("verified") or not reference.get("path") or not reference.get("sha256"):
        raise PipelineError("ASR_SOURCE_UNVERIFIED", "视频需要已校验的本地源文件引用，请重新导入")
    path = Path(reference["path"])
    try:
        if not path.is_file():
            raise OSError("missing video")
        if file_sha256(path).lower() != reference["sha256"].lower():
            raise PipelineError("ASR_SOURCE_CHANGED", "视频原文件已变化，请重新导入", 409)
    except OSError as error:
        raise PipelineError("ASR_SOURCE_NOT_FOUND", "视频原文件不存在或无法读取") from error
    return path


def _identity(cache_file):
    meta = cache_file.media_metadata
    required = ("video_stream_index", "audio_stream_index", "audio_offset_ms", "duration_ms", "timeline_start_ms")
    if any(type(meta.get(key)) is not int for key in required) or meta["duration_ms"] <= 0:
        raise PipelineError("VIDEO_METADATA_UNAVAILABLE", "视频缺少有效音轨元数据，请重新导入")
    return {"version": EXTRACTION_VERSION, "source_sha256": cache_file.source_ref["sha256"],
            **{key: meta[key] for key in required}, "sample_rate": SAMPLE_RATE, "channels": 1}


def _artifact(project_id, cache_file, context, *, preview=False):
    _cancelled(context)
    source = verified_video_source(cache_file)
    identity = _identity(cache_file)
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    directory = video_cache_directory(project_id, cache_file.file_id)
    directory.mkdir(parents=True, exist_ok=True)
    name = ("preview-" if preview else "audio-") + fingerprint
    suffix = source.suffix.lower() if preview else ".wav"
    target, manifest = directory / (name + suffix), directory / (name + ".json")
    try:
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        reference = saved["source_ref"]
        if (saved["identity"] == identity and reference["path"] == str(target)
                and target.resolve() == target and target.is_file()
                and file_sha256(target) == reference["sha256"]):
            return saved
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # Do not trust client-provided stream indexes, offsets or durations for a
    # newly decoded artifact, even when the original file's hash matches.
    metadata = probe_video(source)
    if any(metadata[key] != identity[key] for key in
           ("video_stream_index", "audio_stream_index", "audio_offset_ms", "duration_ms", "timeline_start_ms")):
        raise PipelineError("VIDEO_METADATA_CHANGED", "视频音轨信息不一致，请重新导入", 409)
    _progress(context, operation="video_preview" if preview else "video_extract", file_id=cache_file.file_id,
              state="running", current=0, total=1)
    temporary = temporary_manifest = None
    try:
        with NamedTemporaryFile(dir=directory, suffix=suffix, delete=False) as writer:
            temporary = Path(writer.name)
        args = ["-protocol_whitelist", "file,pipe"]
        if preview:
            muxer = {".mp4": "mp4", ".m4v": "mp4", ".mov": "mov", ".mkv": "matroska",
                     ".avi": "avi", ".webm": "webm", ".wmv": "asf", ".flv": "flv"}[suffix]
            args += ["-copyts", "-start_at_zero", "-i", str(source),
                     "-map", f"0:{identity['video_stream_index']}", "-map", f"0:{identity['audio_stream_index']}",
                     "-c", "copy", "-sn", "-dn", "-map_metadata", "-1", "-disposition:a:0", "default", "-f", muxer]
        else:
            offset_samples = round(identity["audio_offset_ms"] * SAMPLE_RATE / 1000)
            total_samples = max(1, round(identity["duration_ms"] * SAMPLE_RATE / 1000))
            filters = ["asetpts=PTS-STARTPTS", f"aresample={SAMPLE_RATE}:async=1:first_pts=0"]
            if offset_samples > 0:
                filters.append(f"adelay={offset_samples}S:all=1")
            elif offset_samples < 0:
                filters.extend([f"atrim=start_sample={-offset_samples}", "asetpts=PTS-STARTPTS"])
            filters.extend(["apad", f"atrim=end_sample={total_samples}"])
            args += ["-i", str(source), "-map", f"0:{identity['audio_stream_index']}", "-vn", "-sn", "-dn",
                     "-map_metadata", "-1", "-af", ",".join(filters), "-ac", "1", "-ar", str(SAMPLE_RATE),
                     "-c:a", "pcm_s16le", "-f", "wav"]
        _run_ffmpeg(args, temporary, context)
        verified_video_source(cache_file)
        _cancelled(context)
        asset_metadata = probe_video(temporary) if preview else probe_audio(temporary)
        digest = file_sha256(temporary)
        temporary.replace(target)
        saved = {"identity": identity, "source_ref": {"path": str(target), "sha256": digest, "verified": True},
                 "media_metadata": asset_metadata}
        with NamedTemporaryFile("w", encoding="utf-8", dir=directory, suffix=".json", delete=False) as writer:
            temporary_manifest = Path(writer.name)
            json.dump(saved, writer, ensure_ascii=False)
        temporary_manifest.replace(manifest)
        return saved
    finally:
        for path in (temporary, temporary_manifest):
            if path is not None:
                path.unlink(missing_ok=True)


def prepare_video_audio(project_id, cache_file, context=None):
    try:
        artifact = _artifact(project_id, cache_file, context)
    except OSError as error:
        raise PipelineError("VIDEO_CACHE_UNAVAILABLE", "无法写入视频音轨缓存，请检查目录权限和磁盘空间", 500) from error
    cache_file.extra["video_audio"] = artifact
    _progress(context, operation="video_extract", file_id=cache_file.file_id, state="completed", current=1, total=1)
    return artifact


def prepare_video_preview(project_id, cache_file, context=None):
    try:
        return _artifact(project_id, cache_file, context, preview=True)
    except OSError as error:
        raise PipelineError("VIDEO_CACHE_UNAVAILABLE", "无法写入视频预览缓存，请检查目录权限和磁盘空间", 500) from error
