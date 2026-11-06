"""MiniMax file transcription with sentence timestamps (verbose_json).

Protocol: https://platform.minimax.cn/docs/guides/speech-to-text
"""
import json
import math
import re

import httpx

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.transcription_config import MINIMAX_LANGUAGES


SUPPORTED_FORMATS = frozenset("wav aiff flac m4a mp3 aac opus ogg".split())
MAX_AUDIO_BYTES = 50_000_000
MAX_DURATION_MS = 500_000
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
_MIME = {"wav": "audio/wav", "aiff": "audio/aiff", "flac": "audio/flac",
         "m4a": "audio/mp4", "mp3": "audio/mpeg", "aac": "audio/aac",
         "opus": "audio/ogg", "ogg": "audio/ogg"}


def _cancelled(context):
    if context.is_cancelled():
        raise PipelineError("ASR_CANCELLED", "转录已取消", 409, {"attempts": 0})


def _recognition_settings(config):
    hints = config.get("language_hints", ())
    warnings = []
    if len(hints) > 1 or any(hint not in MINIMAX_LANGUAGES for hint in hints):
        hints = ()
        warnings.append({"code": "ASR_LANGUAGE_HINTS_IGNORED",
                         "message": "已保存的语言提示不适用于 MiniMax 接口，本次使用自动语言识别"})
    if config.get("keep_dialect"):
        warnings.append({"code": "ASR_DIALECT_OPTION_IGNORED",
                         "message": "MiniMax 接口不支持 keep_dialect，未发送此百炼参数"})
    return MINIMAX_LANGUAGES[hints[0]] if hints else None, warnings


def _invalid(message):
    return PipelineError("ASR_INVALID_RESPONSE", message, 502)


def _number(value):
    return (type(value) in (int, float) and 0 <= value <= MAX_DURATION_MS / 1000
            and math.isfinite(value))


def _normalized(payload, duration_ms, config):
    if not isinstance(payload, dict):
        raise _invalid("MiniMax 转录返回结构无效")
    text, rows, duration = payload.get("text"), payload.get("segments"), payload.get("duration")
    if not isinstance(text, str) or not isinstance(rows, list) or not _number(duration):
        raise _invalid("MiniMax 转录文本、分句或时长无效")
    language, warnings = _recognition_settings(config)
    segments = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("text"), str):
            raise _invalid("MiniMax 转录分句无效")
        if not row["text"].strip():
            continue
        start, end = row.get("start"), row.get("end")
        if not _number(start) or not _number(end) or not 0 <= start < end <= duration_ms / 1000:
            raise _invalid("MiniMax 分句时间戳不在本地音频范围内")
        start_ms, end_ms = round(start * 1000), round(end * 1000)
        if not 0 <= start_ms < end_ms <= duration_ms:
            raise _invalid("MiniMax 分句时间戳精度无效")
        speaker = row.get("speaker") if config.get("speaker_diarization_enabled") else None
        segments.append({"text": row["text"], "start_ms": start_ms, "end_ms": end_ms,
                         "speaker_id": str(speaker) if type(speaker) in (str, int) else None})
    if text.strip() and not segments:
        raise _invalid("MiniMax 转录结果缺少逐句时间戳")
    segments.sort(key=lambda segment: (segment["start_ms"], segment["end_ms"]))
    trace_id = payload.get("trace_id", "")
    if not isinstance(trace_id, str) or len(trace_id) > 256:
        raise _invalid("MiniMax 转录请求标识无效")
    result = {"text": text or "".join(segment["text"] for segment in segments),
              "segments": segments, "language": language, "request_id": trace_id,
              "warnings": warnings, "usage": {"duration": duration}}
    serialized = json.dumps(result, ensure_ascii=False)
    if config["api_key"] in serialized or re.search(r"data:[^;\s]+;base64,", serialized, re.I):
        raise _invalid("转录接口返回了不应包含的请求数据")
    return result


def request_transcription(audio_bytes, *, audio_format, sample_rate, duration_ms, config,
                          context=None, retry_context=None):
    context = context or ExecutionContext()
    gate = retry_context or context
    _cancelled(context)
    _cancelled(gate)
    if (audio_format not in SUPPORTED_FORMATS or not isinstance(audio_bytes, bytes) or not audio_bytes
            or len(audio_bytes) > MAX_AUDIO_BYTES or type(duration_ms) is not int
            or not 0 < duration_ms <= MAX_DURATION_MS):
        raise PipelineError("ASR_INVALID_AUDIO", "MiniMax 单次转录要求受支持的音频文件，且不超过 50 MB 和 500 秒",
                            400, {"attempts": 0})
    language, _ = _recognition_settings(config)
    headers = {"Authorization": f"Bearer {config['api_key']}"}
    if language:
        headers["language"] = language
    # verbose_json provides the timestamps needed for subtitles; SSE cannot be
    # combined with this format. Let httpx create the multipart boundary.
    data = {"model": config["model"], "response_format": "verbose_json"}
    files = {"file": (f"audio.{audio_format}", audio_bytes, _MIME[audio_format])}
    timeout = float(config["request_timeout"])
    attempts = 0
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(timeout, 10)), follow_redirects=False) as client:
            _cancelled(context)
            _cancelled(gate)
            attempts = 1
            with client.stream("POST", config["api_url"], headers=headers, data=data, files=files) as response:
                if response.status_code != 200:
                    messages = {401: "MiniMax 鉴权失败，请检查 API Key",
                                403: "MiniMax 接口无访问权限，请检查 API Key 和服务开通状态",
                                402: "MiniMax 账户余额或资源包不足",
                                413: "MiniMax 音频文件超过 50 MB 上限",
                                429: "MiniMax 转录触发限流，请稍后重试"}
                    raise PipelineError("ASR_HTTP_ERROR", messages.get(response.status_code,
                                        f"MiniMax 转录请求失败（HTTP {response.status_code}）"),
                                        502, {"http_status": response.status_code})
                chunks, length = [], 0
                for chunk in response.iter_bytes():
                    _cancelled(context)
                    length += len(chunk)
                    if length > _MAX_RESPONSE_BYTES:
                        raise _invalid("MiniMax 转录响应超过大小限制")
                    chunks.append(chunk)
        try:
            payload = json.loads(b"".join(chunks))
        except (ValueError, UnicodeError):
            raise _invalid("MiniMax 转录返回了无效 JSON") from None
        result = _normalized(payload, duration_ms, config)
        result["attempts"] = attempts
        return result
    except httpx.TransportError:
        # There is no idempotency contract for uploaded audio. A timed-out POST
        # may already be billable, so max_retries must not resend it.
        raise PipelineError("ASR_NETWORK_ERROR", "MiniMax 连接中断或超时；为避免重复计费，未自动重发",
                            502, {"attempts": attempts}) from None
    except PipelineError as error:
        error.details = {**(error.details or {}), "attempts": attempts}
        raise
