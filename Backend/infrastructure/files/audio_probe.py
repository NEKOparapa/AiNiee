"""Local audio metadata probing with no optional Python audio dependencies."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import wave

from Backend.application.pipeline_common import PipelineError


AUDIO_EXTENSIONS = frozenset({
    ".wav", ".wave", ".mp3", ".mp2", ".m4a", ".m4b", ".m4r", ".flac",
    ".ogg", ".oga", ".opus", ".aac", ".wma", ".aif", ".aiff", ".aifc",
    ".ape", ".amr", ".ac3", ".alac", ".mka", ".weba",
})


def _canonical_format(path, container_format, codec_name):
    """Choose a real container alias, never infer a format from suffix alone."""
    containers = [name.strip().lower() for name in container_format.split(",") if name.strip()]
    suffix = path.suffix.lower().lstrip(".")
    preferred = {"wave": "wav", "oga": "ogg", "m4b": "m4a", "m4r": "m4a",
                 "mka": "mkv", "weba": "webm"}.get(suffix, suffix)
    codec = str(codec_name or "").lower()
    # ffprobe's mp3 demuxer also reads MPEG layer I/II; those are not MP3.
    if "mp3" in containers and codec in ("mp1", "mp2"):
        return codec
    if preferred == "opus" and "ogg" in containers and codec == "opus":
        return "opus"
    if preferred == "mkv" and "matroska" in containers:
        return "mkv"
    if preferred == "webm" and "matroska" in containers:
        return "webm" if codec in ("opus", "vorbis") else "mkv"
    if preferred in containers:
        return preferred
    if "mp4" in containers:
        return "mp4"
    if "matroska" in containers:
        return "mkv"
    if "asf" in containers and codec in ("wmav1", "wmav2", "wmapro", "wmalossless", "wmavoice"):
        return "wma"
    # Preserve unrecognized or unsupported formats so the requester can reject
    # them explicitly instead of disguising them as an accepted file extension.
    return containers[0]


def _positive_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (ValueError, TypeError):
        return None


def _wave_metadata(path):
    try:
        with wave.open(str(path), "rb") as stream:
            frames, rate, channels = stream.getnframes(), stream.getframerate(), stream.getnchannels()
        if frames <= 0 or rate <= 0 or channels <= 0:
            raise ValueError("WAV 文件没有有效音频帧")
        return {"duration_ms": max(1, round(frames * 1000 / rate)), "sample_rate": rate,
                "channels": channels, "format": "wav", "size_bytes": path.stat().st_size}
    except (OSError, EOFError, ValueError, wave.Error) as error:
        raise PipelineError("AUDIO_PROBE_FAILED", f"无法读取 WAV 音频元数据: {error}") from error


def probe_audio(path: Path) -> dict:
    """Use ffprobe's first audio stream, falling back to stdlib for PCM WAV."""
    path = Path(path).resolve()
    executable = shutil.which("ffprobe")
    if not executable:
        if path.suffix.lower() in (".wav", ".wave"):
            return _wave_metadata(path)
        raise PipelineError("AUDIO_PROBE_UNAVAILABLE", "读取该音频格式需要本机可用的 ffprobe；未自动安装依赖", 503)
    command = [
        executable, "-v", "error", "-select_streams", "a:0",
        "-show_entries", "format=duration,format_name,size:stream=codec_type,codec_name,sample_rate,channels,duration",
        "-of", "json", "-i", str(path),
    ]
    try:
        completed = subprocess.run(
            command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except FileNotFoundError as error:
        if path.suffix.lower() in (".wav", ".wave"):
            return _wave_metadata(path)
        raise PipelineError("AUDIO_PROBE_UNAVAILABLE", "ffprobe 不可用，请检查本机安装和 PATH", 503) from error
    except subprocess.TimeoutExpired as error:
        raise PipelineError("AUDIO_PROBE_TIMEOUT", "读取音频元数据超时", 408) from error
    except OSError as error:
        raise PipelineError("AUDIO_PROBE_FAILED", f"无法启动 ffprobe: {error}") from error
    if completed.returncode:
        detail = completed.stderr.strip()[-500:]
        raise PipelineError("AUDIO_PROBE_FAILED", f"ffprobe 无法读取音频文件: {detail or '无法识别的音频'}")
    try:
        payload = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        stream = next((value for value in streams if value.get("codec_type") == "audio"), None)
        if stream is None:
            raise PipelineError("NO_AUDIO_STREAM", "文件中没有可用的音频流")
        container = payload.get("format", {})
        duration = _positive_number(stream.get("duration")) or _positive_number(container.get("duration"))
        rate, channels = _positive_number(stream.get("sample_rate")), _positive_number(stream.get("channels"))
        if duration is None or rate is None or channels is None or not rate.is_integer() or not channels.is_integer():
            raise PipelineError("AUDIO_METADATA_UNAVAILABLE", "无法确定音频时长、采样率或声道数")
        raw_format = container.get("format_name")
        if not isinstance(raw_format, str) or not raw_format.strip(", "):
            raise PipelineError("AUDIO_METADATA_UNAVAILABLE", "无法确定音频容器格式")
        audio_format = _canonical_format(path, raw_format, stream.get("codec_name"))
        metadata = {"duration_ms": max(1, round(duration * 1000)), "sample_rate": int(rate),
                    "channels": int(channels), "format": audio_format, "size_bytes": path.stat().st_size}
        if audio_format != raw_format:
            metadata["container_format"] = raw_format
        return metadata
    except PipelineError:
        raise
    except (ValueError, TypeError, AttributeError, OSError) as error:
        raise PipelineError("AUDIO_PROBE_FAILED", "ffprobe 返回了无效的音频元数据") from error
