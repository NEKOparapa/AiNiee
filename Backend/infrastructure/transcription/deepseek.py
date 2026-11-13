"""DeepSeek file ASR: https://api-docs.deepseek.com/zh-cn/guides/asr"""
import json
import re

import httpx

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError


MAX_DURATION_MS = 120_000
MAX_AUDIO_BYTES = 8 * 1024 * 1024
WAV_SAMPLE_RATES = {8000, 16000, 22050, 24000, 32000, 44100, 48000}
MIME_TYPES = {"wav": "audio/wav", "ogg": "audio/ogg", "opus": "audio/ogg"}


def can_upload(metadata, size):
    # The API only recognizes the left channel of stereo input. Downmix it
    # locally, along with files whose codec is unknown (including old projects).
    if size > MAX_AUDIO_BYTES or metadata["duration_ms"] > MAX_DURATION_MS or metadata.get("channels") != 1:
        return False
    if metadata["format"] == "wav":
        return metadata.get("codec_name") == "pcm_s16le" and metadata.get("sample_rate") in WAV_SAMPLE_RATES
    return metadata["format"] in ("ogg", "opus") and metadata.get("codec_name") == "opus"


def _normalized(payload, duration_ms, config):
    if not isinstance(payload, dict):
        raise PipelineError("ASR_INVALID_RESPONSE", "DeepSeek 转录返回结构无效", 502)
    text, usage_ms, identifier = payload.get("text"), payload.get("duration_ms"), payload.get("request_id")
    if (not isinstance(text, str) or type(usage_ms) is not int or not 0 <= usage_ms <= MAX_DURATION_MS
            or not isinstance(identifier, str) or len(identifier) > 256):
        raise PipelineError("ASR_INVALID_RESPONSE", "DeepSeek 转录返回的文本、时长或请求标识无效", 502)
    if any(config["api_key"] in value or re.search(r"data:[^;\s]+;base64,", value, re.I)
           for value in (text, identifier)):
        raise PipelineError("ASR_INVALID_RESPONSE", "转录接口返回了不应包含的请求数据", 502)
    warnings, segments = [], []
    if text.strip():
        segments.append({"text": text, "start_ms": 0, "end_ms": duration_ms, "speaker_id": None})
        warnings.append({"code": "ASR_NO_SENTENCE_TIMESTAMPS", "message": "DeepSeek 仅返回整段文本，已按音频片段保存时间范围"})
    if config.get("language_hints"):
        warnings.append({"code": "ASR_LANGUAGE_HINTS_IGNORED", "message": "DeepSeek 自动识别语种，已忽略语言提示"})
    if config.get("speaker_diarization_enabled"):
        warnings.append({"code": "ASR_SPEAKER_UNSUPPORTED", "message": "DeepSeek 未提供说话人标签"})
    if config.get("keep_dialect"):
        warnings.append({"code": "ASR_DIALECT_OPTION_IGNORED", "message": "DeepSeek 不支持 keep_dialect 参数"})
    return {"text": text, "segments": segments, "language": None, "request_id": identifier,
            "warnings": warnings, "usage": {"duration": usage_ms / 1000}, "attempts": 1}


def request_transcription(audio_bytes, *, audio_format, sample_rate, duration_ms, config,
                          context=None, retry_context=None):
    context = context or ExecutionContext()
    if (audio_format not in MIME_TYPES or not isinstance(audio_bytes, bytes) or not 0 < len(audio_bytes) <= MAX_AUDIO_BYTES
            or type(duration_ms) is not int or not 0 < duration_ms <= MAX_DURATION_MS
            or (audio_format == "wav" and sample_rate not in WAV_SAMPLE_RATES)):
        raise PipelineError("ASR_INVALID_AUDIO", "DeepSeek 要求 120 秒、8 MiB 以内的 PCM WAV 或 Ogg Opus 音频",
                            400, {"attempts": 0})
    headers = {"Authorization": f"Bearer {config['api_key']}"}
    files = {"file": (f"audio.{audio_format}", audio_bytes, MIME_TYPES[audio_format])}
    timeout, attempts = float(config["request_timeout"]), 0
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(timeout, 10)), follow_redirects=False) as client:
            if context.is_cancelled() or (retry_context and retry_context.is_cancelled()):
                raise PipelineError("ASR_CANCELLED", "转录已取消", 409)
            attempts = 1
            with client.stream("POST", config["api_url"], headers=headers, files=files) as response:
                if response.status_code != 200:
                    raise PipelineError("ASR_HTTP_ERROR", f"DeepSeek 转录请求失败（HTTP {response.status_code}）",
                                        502, {"http_status": response.status_code})
                content = bytearray()
                for chunk in response.iter_bytes():
                    if context.is_cancelled():
                        raise PipelineError("ASR_CANCELLED", "转录已取消", 409)
                    content.extend(chunk)
                    if len(content) > 1024 * 1024:
                        raise PipelineError("ASR_INVALID_RESPONSE", "DeepSeek 转录响应超过大小限制", 502)
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeError):
            raise PipelineError("ASR_INVALID_RESPONSE", "DeepSeek 转录返回了无效 JSON", 502) from None
        return _normalized(payload, duration_ms, config)
    except httpx.TransportError:
        raise PipelineError("ASR_NETWORK_ERROR", "DeepSeek 转录连接中断或超时，未自动重发请求",
                            502, {"attempts": attempts}) from None
    except PipelineError as error:
        error.details = {**(error.details or {}), "attempts": attempts}
        raise
