"""DashScope non-realtime Qwen-Audio-ASR HTTP/SSE adapter.

Protocol: https://help.aliyun.com/zh/model-studio/qwen-audio-asr-http-api
Responses are normalized here; credentials and raw payloads never leave this adapter.
"""
import base64
import json
import math
import re

import httpx

from Backend.application.execution_context import ExecutionContext
from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.request_defaults import REQUEST_TIMEOUT_SECONDS


SUPPORTED_FORMATS = frozenset("aac amr avi flac flv m4a mkv mov mp3 mp4 mpeg ogg opus wav webm wma wmv".split())
_MIME = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "opus": "audio/ogg", "mkv": "video/x-matroska",
         "avi": "video/x-msvideo", "flv": "video/x-flv", "mov": "video/quicktime", "mp4": "video/mp4",
         "webm": "audio/webm", "wma": "audio/x-ms-wma", "wmv": "video/x-ms-wmv"}
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def _cancelled(context, attempts=None):
    if context.is_cancelled():
        details = {"attempts": attempts} if attempts is not None else None
        raise PipelineError("ASR_CANCELLED", "转录已取消", 409, details)


def _invalid(message="转录接口返回结构无效"):
    return PipelineError("ASR_INVALID_RESPONSE", message, 502)


def _text(value):
    if not isinstance(value, str):
        raise _invalid("转录接口未返回有效文本")
    return value


def _compact(text):
    return "".join(text.split())


def _interval(start, end, duration_ms):
    if type(start) is not int or type(end) is not int or start < 0 or end <= start or end > duration_ms:
        raise _invalid("转录时间戳必须是音频范围内的有效毫秒区间")
    return start, end


def _speaker(value):
    if value is None:
        return None
    if type(value) is int and value >= 0:
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        return value
    raise _invalid("转录说话人标识无效")


class _Accumulator:
    def __init__(self, duration_ms):
        self.duration_ms = duration_ms
        self.text = None
        self.sentences = {}
        self.sentence_versions = {}
        self.usage = {}
        self.request_id = ""
        self.events = 0
        self.language = None

    def add(self, payload):
        if not isinstance(payload, dict):
            raise _invalid()
        if payload.get("code") not in (None, "", "200", 200, "Success", "success"):
            raise PipelineError("ASR_PROVIDER_ERROR", "转录接口拒绝了请求，请检查模型和接口配置", 502)
        output = payload.get("output")
        if not isinstance(output, dict):
            raise _invalid("转录接口缺少 output 结果")
        self.events += 1
        if "text" in output:
            text = _text(output["text"])
            # Some streams finish with an empty control packet, not a text reset.
            if text.strip() or self.text is None:
                self.text = text
        language = output.get("language")
        if isinstance(language, str) and re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,8})?", language):
            self.language = language
        rows = []
        if "sentences" in output:
            if not isinstance(output["sentences"], list):
                raise _invalid("转录句子列表无效")
            rows.extend(output["sentences"])
        if "sentence" in output and output["sentence"] is not None:
            rows.append(output["sentence"])
        for row in rows:
            if isinstance(row, dict) and not row.get("text") and not row.get("words"):
                continue
            if not isinstance(row, dict) or type(row.get("sentence_id")) is not int or row["sentence_id"] < 0:
                raise _invalid("转录句子缺少有效编号")
            channel = row.get("channel_id", 0)
            if type(channel) is not int or channel < 0:
                raise _invalid("转录声道编号无效")
            if "sentence_end" in row and not isinstance(row["sentence_end"], bool):
                raise _invalid("转录句子结束标记无效")
            _text(row.get("text", ""))
            self.sentences[(channel, row["sentence_id"])] = row
            self.sentence_versions[(channel, row["sentence_id"])] = self.events
        usage = payload.get("usage", {})
        if not isinstance(usage, dict):
            raise _invalid("转录用量信息无效")
        for key in ("duration", "input_tokens", "output_tokens", "total_tokens"):
            if key in usage:
                value = usage[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise _invalid("转录用量信息无效")
                # SSE usage is cumulative; do not charge it once per sentence.
                self.usage[key] = max(self.usage.get(key, 0), value)
        request_id = payload.get("request_id")
        if isinstance(request_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", request_id):
            self.request_id = request_id

    def finish(self):
        if not self.events or (self.text is None and not self.sentences):
            raise _invalid("转录接口未返回识别结果")
        segments, unfinished, completed = [], [], []
        timeline = {}
        provisional, timed_snapshots, sentence_segments = [], [], []
        for key, row in self.sentences.items():
            channel, _ = key
            version = self.sentence_versions[key]
            words = row.get("words")
            if words is not None and not isinstance(words, list):
                raise _invalid("转录词时间戳列表无效")
            stable_words = []
            for word in words or []:
                if not isinstance(word, dict) or not isinstance(word.get("fixed"), bool):
                    raise _invalid("转录词时间戳缺少稳定标记")
                if word["fixed"]:
                    begin, end = _interval(word.get("begin_time"), word.get("end_time"), self.duration_ms)
                    stable_words.append({"text": _text(word.get("text", "")) + _text(word.get("punctuation", "")),
                                         "start_ms": begin, "end_ms": end,
                                         "speaker_id": _speaker(row.get("speaker_id"))})
            row_text = _text(row.get("text", "")).strip()
            if not row_text:
                continue
            all_words_fixed = bool(words) and len(stable_words) == len(words)
            final = row.get("sentence_end") is True
            word_text = _compact("".join(word["text"] for word in stable_words))
            compact_row = _compact(row_text)
            # Japanese cumulative snapshots can prepend a comma to sentence.text
            # that appears in neither the fixed words nor authoritative output.text.
            # Accept only that proven redundant prefix, never missing spoken text.
            redundant_comma = (word_text == compact_row.lstrip("、，,") and self.text is not None
                               and _compact(self.text).startswith(word_text))
            words_cover_text = all_words_fixed and (word_text == compact_row or redundant_comma)
            snapshot = (channel, row_text, version, row.get("begin_time"))
            if not final and not ("sentence_end" not in row and words_cover_text):
                unfinished.append(snapshot)
                continue
            completed.append(snapshot)
            if words and not all_words_fixed:
                # Text can be final before fine-grained word timing stabilizes.
                # Preserve that text, but never publish provisional word times.
                provisional.append(snapshot)
                continue
            if all_words_fixed:
                previous = -1
                for word in stable_words:
                    if word["start_ms"] < previous:
                        raise _invalid("转录词时间戳顺序无效")
                    previous = word["start_ms"]
            if words_cover_text:
                # Qwen 3.1 can change sentence_id while sending the cumulative
                # word prefix again. Fixed timestamps identify the same word.
                for word in stable_words:
                    timeline[(channel, word["start_ms"], word["end_ms"])] = word
                timed_snapshots.append((channel, row_text, version, stable_words[0]["start_ms"]))
                continue
            if row.get("begin_time") is not None and row.get("end_time") is not None:
                start, end = _interval(row["begin_time"], row["end_time"], self.duration_ms)
            elif all_words_fixed:
                start, end = _interval(stable_words[0]["start_ms"], stable_words[-1]["end_ms"], self.duration_ms)
            else:
                raise _invalid("转录最终句子缺少时间戳")
            sentence_segments.append((snapshot, {"text": row_text, "start_ms": start, "end_ms": end,
                                                 "speaker_id": _speaker(row.get("speaker_id"))}))

        def covered_by_later(snapshot, candidates):
            channel, text, version, begin = snapshot
            return any(channel == next_channel and next_version > version
                       and type(begin) is int and type(next_begin) is int and next_begin <= begin
                       and _compact(next_text).startswith(_compact(text))
                       for next_channel, next_text, next_version, next_begin in candidates)

        # Final cumulative words can stabilize several earlier sentence IDs at
        # once. Earlier provisional timing must not force a permanent downgrade.
        coarse = any(not covered_by_later(snapshot, timed_snapshots) for snapshot in provisional)
        segments.extend(segment for snapshot, segment in sentence_segments
                        if not covered_by_later(snapshot, timed_snapshots))
        # An unfinished snapshot may have been superseded by a later cumulative
        # final sentence. EOF alone must not make an unfinished tail successful.
        if any(not covered_by_later(snapshot, completed) for snapshot in unfinished):
            raise PipelineError("ASR_INCOMPLETE_RESPONSE", "转录返回尚未完成的文本，请重试", 502)
        current, current_channel = None, None
        ordered_words = sorted(timeline.items(), key=lambda entry: (entry[0][0], entry[0][1], entry[0][2]))
        for (channel, _, _), word in ordered_words:
            if current is not None and (channel != current_channel or word["speaker_id"] != current["speaker_id"]
                                        or word["start_ms"] - current["end_ms"] >= 800):
                if current["text"].strip():
                    current["text"] = current["text"].strip()
                    segments.append(current)
                current = None
            if current is None:
                current, current_channel = dict(word), channel
                current["words"] = [dict(word)]
            else:
                current["text"] += word["text"]
                current["end_ms"] = word["end_ms"]
                current["words"].append(dict(word))
            if re.search(r"[.!?。！？][\"'”’）)\]]*\s*$", word["text"]):
                current["text"] = current["text"].strip()
                segments.append(current)
                current = None
        if current is not None and current["text"].strip():
            current["text"] = current["text"].strip()
            segments.append(current)
        segments.sort(key=lambda segment: (segment["start_ms"], segment["end_ms"]))
        joined = "".join(segment["text"] for segment in segments)
        text = self.text.strip() if self.text is not None else joined
        warnings = []
        if text and (coarse or _compact(text) != _compact(joined)):
            segments = [{"text": text, "start_ms": 0, "end_ms": self.duration_ms, "speaker_id": None}]
            warnings.append({"code": "ASR_COARSE_TIMESTAMPS", "message": "接口未返回覆盖全文的完整句级时间戳，已保留全文并使用整个音频区间"})
        elif not text and joined:
            text = joined
        return {"text": text, "segments": segments, "usage": self.usage,
                "request_id": self.request_id, "warnings": warnings, "language": self.language}


def _decode_event(data):
    try:
        return json.loads(data)
    except (ValueError, TypeError):
        raise _invalid("转录接口返回的 JSON 无效") from None


def _read_response(response, accumulator, context):
    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" not in content_type:
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            _cancelled(context)
            size += len(chunk)
            if size > _MAX_RESPONSE_BYTES:
                raise _invalid("转录接口响应过大")
            chunks.append(chunk)
        accumulator.add(_decode_event(b"".join(chunks)))
        return
    data_lines, size = [], 0
    for line in response.iter_lines():
        _cancelled(context)
        size += len(line)
        if size > _MAX_RESPONSE_BYTES:
            raise _invalid("转录接口响应过大")
        if not line:
            if data_lines:
                data = "\n".join(data_lines)
                data_lines = []
                if data.strip() == "[DONE]":
                    return
                accumulator.add(_decode_event(data))
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip(" "))
    if data_lines:
        data = "\n".join(data_lines)
        if data.strip() != "[DONE]":
            accumulator.add(_decode_event(data))


def request_transcription(audio_bytes, *, audio_format, sample_rate, duration_ms, config, context=None,
                          retry_context=None):
    """Receive using context; optionally gate each new POST with retry_context.

    Long-audio callers can drain an already sent request while their parent
    operation is cancelled. The separate gate still prevents any new retries.
    """
    context = context or ExecutionContext()
    request_gate = retry_context or context
    _cancelled(context, attempts=0)
    _cancelled(request_gate, attempts=0)
    if audio_format not in SUPPORTED_FORMATS or not isinstance(audio_bytes, bytes) or not audio_bytes:
        raise PipelineError("ASR_INVALID_AUDIO", "音频格式无效或内容为空", 400)
    if type(duration_ms) is not int or not 0 < duration_ms <= 300000:
        raise PipelineError("ASR_AUDIO_TOO_LONG", "当前转录支持时长不超过 5 分钟的音频", 400)
    if sample_rate is not None and (type(sample_rate) is not int or sample_rate <= 0):
        raise PipelineError("ASR_INVALID_AUDIO", "音频采样率无效", 400)
    mime = _MIME.get(audio_format, f"audio/{audio_format}")
    parameters = {"format": audio_format, "speaker_diarization_enabled": config.get("speaker_diarization_enabled", False),
                  "keep_dialect": config.get("keep_dialect", False)}
    if sample_rate:
        parameters["sample_rate"] = str(sample_rate)
    if config.get("language_hints"):
        parameters["language_hints"] = list(config["language_hints"])
    payload = {"model": config["model"], "input": {"messages": [{"role": "user", "content": [
        {"type": "input_audio", "input_audio": {"data": f"data:{mime};base64," + base64.b64encode(audio_bytes).decode("ascii")}}
    ]}]}, "parameters": parameters}
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json",
               "X-DashScope-SSE": "enable" if config.get("stream", True) else "disable"}
    max_attempts = 1 + config.get("max_retries", 0)
    with httpx.Client(timeout=config.get("request_timeout", REQUEST_TIMEOUT_SECONDS), follow_redirects=False) as client:
        for attempt in range(1, max_attempts + 1):
            _cancelled(context, attempts=attempt - 1)
            _cancelled(request_gate, attempts=attempt - 1)
            retryable = False
            accumulator = None
            try:
                with client.stream("POST", config["api_url"], headers=headers, json=payload) as response:
                    if response.status_code >= 400 or response.is_redirect:
                        retryable = response.status_code in (408, 429) or response.status_code >= 500
                        status = response.status_code
                        message = "转录接口鉴权失败，请检查 API Key 和地域" if status in (401, 403) else f"转录接口请求失败（HTTP {status}）"
                        error = PipelineError("ASR_HTTP_ERROR", message, 502, {"http_status": status, "attempts": attempt})
                    else:
                        accumulator = _Accumulator(duration_ms)
                        _read_response(response, accumulator, context)
                        result = accumulator.finish()
                        # Reject echoes of request credentials/audio instead of persisting them.
                        serialized = json.dumps(result, ensure_ascii=False)
                        if config["api_key"] in serialized or re.search(r"data:[^;\s]+;base64,", serialized, re.I):
                            raise _invalid("转录接口返回了不应包含的请求数据")
                        result["attempts"] = attempt
                        if parameters["speaker_diarization_enabled"] and config.get("language_hints"):
                            result["warnings"].append({"code": "ASR_LANGUAGE_HINTS_IGNORED", "message": "启用说话人分离时，百炼不使用 language_hints"})
                        return result
            except PipelineError as error:
                # Receiving a short request can still be cancelled mid-stream.
                # Its already issued POST must not be reported as zero attempts.
                error.details = {**(error.details or {}), "attempts": attempt}
                raise
            except httpx.TransportError:
                error = PipelineError("ASR_NETWORK_ERROR", "转录接口连接中断或超时", 502, {"attempts": attempt})
                # A POST that already produced ASR events may be billable. Never
                # silently submit that audio again after a truncated response.
                retryable = accumulator is None or accumulator.events == 0
            if not retryable or attempt == max_attempts:
                raise error from None
            _cancelled(context, attempts=attempt)
            _cancelled(request_gate, attempts=attempt)
            if request_gate.cancel_event.wait(min(2 ** (attempt - 1), 8)):
                _cancelled(request_gate, attempts=attempt)
    raise PipelineError("ASR_NETWORK_ERROR", "转录接口未完成请求", 502)
