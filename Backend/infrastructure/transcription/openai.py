"""OpenAI multipart file transcription; never repeat an uncertain paid POST."""
import json
import math
import re

import httpx

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.openai_media import openai_media_endpoint


SUPPORTED_FORMATS = frozenset("flac mp3 mp4 mpeg mpga m4a ogg wav webm".split())
MAX_AUDIO_BYTES = 25_000_000
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
_MIME = {"flac": "audio/flac", "mp3": "audio/mpeg", "mp4": "audio/mp4", "mpeg": "audio/mpeg",
         "mpga": "audio/mpeg", "m4a": "audio/mp4", "ogg": "audio/ogg", "wav": "audio/wav", "webm": "audio/webm"}


def _cancelled(context):
    if context.is_cancelled():
        raise PipelineError("ASR_CANCELLED", "转录已取消", 409, {"attempts": 0})


def _settings(config):
    model = config["model"].lower()
    diarized = model.startswith("gpt-4o-transcribe-diarize")
    text_only = not diarized and model.startswith(("gpt-transcribe", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"))
    data = {"model": config["model"], "response_format": "diarized_json" if diarized else
            "json" if text_only else "verbose_json"}
    warnings = []
    if diarized:
        data["chunking_strategy"] = "auto"
    elif not text_only:
        data["timestamp_granularities[]"] = "segment"
    hints = config.get("language_hints", ())
    if model.startswith("gpt-transcribe") and hints:
        data["languages[]"] = list(hints)
    elif len(hints) == 1:
        data["language"] = hints[0]
    elif hints:
        warnings.append({"code": "ASR_LANGUAGE_HINTS_IGNORED",
                         "message": "当前 OpenAI 模型只接受一种语言提示，本次使用自动识别"})
    if config.get("keep_dialect"):
        warnings.append({"code": "ASR_DIALECT_OPTION_IGNORED", "message": "OpenAI 转录不发送 keep_dialect 参数"})
    if config.get("speaker_diarization_enabled") and not diarized:
        warnings.append({"code": "ASR_SPEAKER_UNSUPPORTED",
                         "message": "当前 OpenAI 模型未提供说话人分离；需要说话人标签时请选择支持该功能的模型"})
    return data, warnings


def _invalid(message):
    return PipelineError("ASR_INVALID_RESPONSE", message, 502)


def _number(value):
    return type(value) in (int, float) and 0 <= value <= 10 ** 12 and math.isfinite(value)


def _normalized(payload, duration_ms, config, request_id):
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str) or payload.get("error"):
        raise _invalid("OpenAI 转录返回结构无效")
    data, warnings = _settings(config)
    text, segments = payload["text"], []
    rows = payload.get("segments")
    if rows is None and data["response_format"] == "json":
        if text.strip():
            segments.append({"text": text, "start_ms": 0, "end_ms": duration_ms, "speaker_id": None})
            warnings.append({"code": "ASR_NO_SENTENCE_TIMESTAMPS",
                             "message": "当前 OpenAI 模型未返回逐句时间戳，已按整段音频保存原文"})
    elif not isinstance(rows, list):
        raise _invalid("OpenAI 转录结果缺少逐句时间戳")
    else:
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise _invalid("OpenAI 转录分句无效")
            if not row["text"].strip():
                continue
            start, end = row.get("start"), row.get("end")
            if not _number(start) or not _number(end) or not start < end <= duration_ms / 1000 + 0.001:
                raise _invalid("OpenAI 分句时间戳不在本地音频范围内")
            start_ms, end_ms = round(start * 1000), min(duration_ms, round(end * 1000))
            if not 0 <= start_ms < end_ms <= duration_ms:
                raise _invalid("OpenAI 分句时间戳精度无效")
            speaker = row.get("speaker") if config.get("speaker_diarization_enabled") else None
            segments.append({"text": row["text"], "start_ms": start_ms, "end_ms": end_ms,
                             "speaker_id": str(speaker) if type(speaker) in (str, int) else None})
        if text.strip() and not segments:
            raise _invalid("OpenAI 转录结果缺少有效分句")
    segments.sort(key=lambda segment: (segment["start_ms"], segment["end_ms"]))
    usage = {"duration": duration_ms / 1000}
    raw_usage = payload.get("usage")
    if isinstance(raw_usage, dict):
        usage.update({key: raw_usage[key] for key in ("input_tokens", "output_tokens", "total_tokens")
                      if type(raw_usage.get(key)) is int and 0 <= raw_usage[key] <= 10 ** 12})
        if _number(raw_usage.get("seconds")):
            usage["duration"] = raw_usage["seconds"]
    # Whisper reports language names, whereas gpt-transcribe reports ISO codes.
    # Let the existing language detector handle names rather than storing them as codes.
    language = payload.get("language")
    languages = payload.get("languages")
    if isinstance(languages, list) and len(languages) == 1 and isinstance(languages[0], dict):
        language = languages[0].get("code")
    if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?", language):
        hints = config.get("language_hints", ())
        language = hints[0] if len(hints) == 1 else None
    identifier = request_id if re.fullmatch(r"[A-Za-z0-9_-]{0,128}", request_id) else ""
    result = {"text": text, "segments": segments, "language": language, "request_id": identifier,
              "warnings": warnings, "usage": usage}
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
            or len(audio_bytes) > MAX_AUDIO_BYTES or type(duration_ms) is not int or duration_ms <= 0):
        raise PipelineError("ASR_INVALID_AUDIO", "OpenAI 转录要求受支持的音频文件，且单次不超过 25 MB", 400, {"attempts": 0})
    data, _ = _settings(config)
    endpoint = openai_media_endpoint(config["api_url"], "/audio/transcriptions")
    timeout, attempts = float(config["request_timeout"]), 0
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(timeout, 10)), follow_redirects=False) as client:
            _cancelled(context)
            _cancelled(gate)
            attempts = 1
            with client.stream("POST", endpoint, headers={"Authorization": f"Bearer {config['api_key']}"},
                               data=data, files={"file": (f"audio.{audio_format}", audio_bytes, _MIME[audio_format])}) as response:
                if response.status_code != 200:
                    raise PipelineError("ASR_HTTP_ERROR", f"OpenAI 转录请求失败（HTTP {response.status_code}），请检查密钥、模型及额度",
                                        502, {"http_status": response.status_code})
                content = bytearray()
                for chunk in response.iter_bytes():
                    _cancelled(context)
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise _invalid("OpenAI 转录响应超过大小限制")
                request_id = response.headers.get("x-request-id", "")
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeError):
            raise _invalid("OpenAI 转录返回了无效 JSON") from None
        return {**_normalized(payload, duration_ms, config, request_id), "attempts": attempts}
    except httpx.TransportError:
        raise PipelineError("ASR_NETWORK_ERROR", "OpenAI 转录连接中断或超时；为避免重复计费，未自动重发",
                            502, {"attempts": attempts}) from None
    except PipelineError as error:
        error.details = {**(error.details or {}), "attempts": attempts}
        raise
