"""Doubao Base64 flash recording recognition.

Official protocol:
https://docs.volcengine.com/docs/doubao-voice/large-model-recording-file-lite-recognition-api
"""
import base64
import json
import re
import uuid

import httpx

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.transcription_config import VOLCENGINE_LANGUAGES


FAST_FORMATS = frozenset("wav mp3 ogg opus".split())
FAST_MAX_BYTES = 100 * 1024 * 1024
FAST_MAX_DURATION_MS = 2 * 60 * 60 * 1000
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def _cancelled(context, attempts=0):
    if context.is_cancelled():
        raise PipelineError("ASR_CANCELLED", "已停止等待转录", 409,
                            {"attempts": attempts})


def _headers(config, request_id):
    headers = {"Content-Type": "application/json", "X-Api-Resource-Id": config["resource_id"],
               "X-Api-Request-Id": request_id, "X-Api-Sequence": "-1"}
    if config.get("app_id"):
        headers.update({"X-Api-App-Key": config["app_id"], "X-Api-Access-Key": config["api_key"]})
    else:
        headers["X-Api-Key"] = config["api_key"]
    return headers


def _recognition_settings(config):
    hints = config.get("language_hints", ())
    warnings = []
    if len(hints) > 1 or any(hint not in VOLCENGINE_LANGUAGES for hint in hints):
        hints = ()
        warnings.append({"code": "ASR_LANGUAGE_HINTS_IGNORED", "message": "已保存的语言提示不适用于火山接口，本次使用接口默认语言识别"})
    speaker = config.get("speaker_diarization_enabled", False)
    if speaker and hints and hints[0] != "zh":
        speaker = False
        warnings.append({"code": "ASR_SPEAKER_UNSUPPORTED", "message": "火山接口在当前指定语种下不支持说话人分离，本次保留文本识别"})
    if config.get("keep_dialect"):
        warnings.append({"code": "ASR_DIALECT_OPTION_IGNORED", "message": "火山接口不支持 keep_dialect，未发送此百炼参数"})
    return hints, speaker, warnings


def _body(audio, audio_format, sample_rate, config):
    audio = {**audio, "format": "ogg" if audio_format == "opus" else audio_format, "rate": sample_rate}
    if audio_format == "opus":
        audio["codec"] = "opus"
    hints, speaker, _ = _recognition_settings(config)
    if hints:
        audio["language"] = VOLCENGINE_LANGUAGES[hints[0]]
    return {"user": {"uid": "ainiee"}, "audio": audio,
            "request": {"model_name": "bigmodel", "show_utterances": True,
                        "enable_speaker_info": speaker,
                        "enable_itn": True, "enable_punc": True}}


def _post(client, url, body, headers, context):
    """Read a bounded response without exposing server messages or request URLs."""
    with client.stream("POST", url, json=body, headers=headers) as response:
        if response.status_code != 200:
            message = ("火山鉴权失败，请检查 API Key、应用 ID 和资源开通状态"
                       if response.status_code in (401, 403) else f"火山转录请求失败（HTTP {response.status_code}）")
            raise PipelineError("ASR_HTTP_ERROR", message, 502, {"http_status": response.status_code})
        chunks, length = [], 0
        for chunk in response.iter_bytes():
            _cancelled(context)
            length += len(chunk)
            if length > _MAX_RESPONSE_BYTES:
                raise PipelineError("ASR_INVALID_RESPONSE", "火山转录响应超过大小限制", 502)
            chunks.append(chunk)
        content = b"".join(chunks)
        try:
            payload = json.loads(content) if content.strip() else {}
        except (ValueError, UnicodeError):
            raise PipelineError("ASR_INVALID_RESPONSE", "火山转录返回了无效 JSON", 502) from None
        if not isinstance(payload, dict):
            raise PipelineError("ASR_INVALID_RESPONSE", "火山转录返回结构无效", 502)
        code = str(response.headers.get("X-Api-Status-Code", payload.get("X-Api-Status-Code", "")))
        if not re.fullmatch(r"[0-9]{8}", code):
            raise PipelineError("ASR_INVALID_RESPONSE", "火山转录响应缺少有效状态码", 502)
        return code, payload


def _service_error(code):
    messages = {"45000001": "火山请求参数无效，请检查接口配置",
                "45000002": "火山未读取到有效音频", "45000131": "火山音频提交时长配额已达上限",
                "45000132": "音频超过火山极速版大小限制", "45000151": "火山不支持此音频格式",
                "55000031": "火山服务繁忙，请稍后重试"}
    message = messages.get(code, f"火山转录请求失败（状态码 {code}）")
    return PipelineError("ASR_PROVIDER_ERROR", message, 502)


def _normalized(payload, duration_ms, config, request_id, *, silent=False):
    result = payload.get("result", {})
    if not isinstance(result, dict):
        raise PipelineError("ASR_INVALID_RESPONSE", "火山转录结果结构无效", 502)
    text = result.get("text", "")
    utterances = result.get("utterances", [])
    if not isinstance(text, str) or not isinstance(utterances, list):
        raise PipelineError("ASR_INVALID_RESPONSE", "火山转录文本或分句结构无效", 502)
    hints, _, warnings = _recognition_settings(config)
    segments = []
    if not silent:
        for row in utterances:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise PipelineError("ASR_INVALID_RESPONSE", "火山转录分句无效", 502)
            if not row["text"].strip():
                continue
            start, end = row.get("start_time"), row.get("end_time")
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration_ms:
                raise PipelineError("ASR_INVALID_RESPONSE", "火山分句时间戳不在本地音频范围内", 502)
            additions = row.get("additions", {})
            speaker = additions.get("speaker") if isinstance(additions, dict) else None
            segment = {"text": row["text"], "start_ms": start, "end_ms": end,
                       "speaker_id": str(speaker) if isinstance(speaker, (str, int)) and not isinstance(speaker, bool) else None}
            words = row.get("words")
            if isinstance(words, list):
                valid_words = []
                for word in words:
                    if not isinstance(word, dict):
                        valid_words = []
                        break
                    begin, finish = word.get("start_time"), word.get("end_time")
                    if (type(begin) is not int or type(finish) is not int or not isinstance(word.get("text"), str)
                            or not start <= begin <= finish <= end):
                        valid_words = []
                        break
                    if begin < finish:
                        valid_words.append({"text": word["text"], "start_ms": begin, "end_ms": finish})
                if valid_words:
                    segment["words"] = valid_words
            segments.append(segment)
        if not segments and text.strip():
            segments = [{"text": text, "start_ms": 0, "end_ms": duration_ms, "speaker_id": None}]
            warnings.append({"code": "ASR_NO_SENTENCE_TIMESTAMPS", "message": "接口未返回分句时间戳，已按整段音频保存原文"})
    else:
        text = ""
    if not text:
        text = "".join(segment["text"] for segment in segments)
    normalized = {"text": text, "segments": segments, "language": next(iter(hints), None),
                  "request_id": request_id, "warnings": warnings,
                  "usage": {"duration": duration_ms / 1000}}
    serialized = json.dumps(normalized, ensure_ascii=False)
    if (config["api_key"] in serialized
            or re.search(r"data:[^;\s]+;base64,", serialized, re.I)):
        raise PipelineError("ASR_INVALID_RESPONSE", "转录接口返回了不应包含的请求数据", 502)
    return normalized


def request_fast(audio_bytes, *, audio_format, sample_rate, duration_ms, config, context=None, retry_context=None):
    context = context or ExecutionContext()
    gate = retry_context or context
    _cancelled(context)
    _cancelled(gate)
    if (audio_format not in FAST_FORMATS or not isinstance(audio_bytes, bytes) or not audio_bytes
            or len(audio_bytes) > FAST_MAX_BYTES or not 0 < duration_ms <= FAST_MAX_DURATION_MS):
        raise PipelineError("ASR_INVALID_AUDIO", "火山极速版要求 WAV、MP3 或 OGG OPUS，单次不超过 100 MB 和 2 小时", 400,
                            {"attempts": 0})
    request_id = str(uuid.uuid4())
    body = _body({"data": base64.b64encode(audio_bytes).decode("ascii")}, audio_format, sample_rate, config)
    timeout = float(config["request_timeout"])
    _cancelled(gate)
    try:
        # No automatic retry: an interrupted POST can already have incurred usage.
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(timeout, 10)), follow_redirects=False) as client:
            code, payload = _post(client, config["api_url"], body, _headers(config, request_id), context)
        if code not in ("20000000", "20000003"):
            raise _service_error(code)
        result = _normalized(payload, duration_ms, config, request_id, silent=code == "20000003")
        result["attempts"] = 1
        return result
    except httpx.TransportError:
        raise PipelineError("ASR_NETWORK_ERROR", "火山极速版连接中断或超时；为避免重复计费，未自动重发", 502,
                            {"attempts": 1}) from None
    except PipelineError as error:
        error.details = {**(error.details or {}), "attempts": 1}
        raise
