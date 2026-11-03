"""Probe local video streams and select one deterministic spoken-audio track."""
import json
import math
import os
from pathlib import Path
import subprocess

from Backend.application.pipeline_common import PipelineError
from Backend.core.media_tools import find_media_tool, missing_media_tool_message


VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv", ".flv"})


def _number(value, default=None):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def probe_video(path):
    path = Path(path)
    executable = find_media_tool("ffprobe")
    if not executable:
        raise PipelineError("VIDEO_PROBE_UNAVAILABLE", missing_media_tool_message("ffprobe"), 503)
    command = [executable, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams",
               "-of", "json", "-i", str(path)]
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except FileNotFoundError as error:
        raise PipelineError("VIDEO_PROBE_UNAVAILABLE", missing_media_tool_message("ffprobe"), 503) from error
    except subprocess.TimeoutExpired as error:
        raise PipelineError("VIDEO_PROBE_TIMEOUT", "读取视频元数据超时", 408) from error
    except OSError as error:
        raise PipelineError("VIDEO_PROBE_FAILED", "无法启动视频探测") from error
    if result.returncode:
        raise PipelineError("VIDEO_PROBE_FAILED", "视频无法解码或文件已损坏")
    try:
        payload = json.loads(result.stdout)
        streams = payload["streams"]
        videos = [s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")]
        audios = sorted((s for s in streams if s.get("codec_type") == "audio"), key=lambda s: s["index"])
        if not videos:
            raise PipelineError("NO_VIDEO_STREAM", "文件没有有效的视频画面")
        if not audios:
            raise PipelineError("NO_AUDIO_STREAM", "视频没有可翻译的音轨")
        video = next((s for s in videos if s.get("disposition", {}).get("default")), videos[0])
        audio = next((s for s in audios if s.get("disposition", {}).get("default")), audios[0])
        container = payload.get("format", {})
        origin = _number(container.get("start_time"), _number(video.get("start_time"), 0))
        duration = _number(container.get("duration"), _number(video.get("duration")))
        if duration is None or duration <= 0:
            raise PipelineError("VIDEO_METADATA_UNAVAILABLE", "无法确定视频时长")
        audio_start = _number(audio.get("start_time"), origin)
        return {
            "duration_ms": max(1, round(duration * 1000)), "format": path.suffix.lower().lstrip("."),
            "container_format": str(container.get("format_name", "")), "size_bytes": path.stat().st_size,
            "width": int(video.get("width", 0)), "height": int(video.get("height", 0)),
            "video_stream_index": int(video["index"]), "audio_stream_index": int(audio["index"]),
            "audio_track_index": audios.index(audio), "audio_stream_count": len(audios),
            "timeline_start_ms": round(origin * 1000), "audio_offset_ms": round((audio_start - origin) * 1000),
            "audio_language": str(audio.get("tags", {}).get("language", "")),
            "audio_title": str(audio.get("tags", {}).get("title", "")),
        }
    except PipelineError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError, OSError) as error:
        raise PipelineError("VIDEO_PROBE_FAILED", "视频元数据无效") from error
