"""Read-only, per-call configuration for the independent online ASR provider."""
import copy
import json
import math
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

from Backend.application.pipeline_common import PipelineError
from Backend.domain.config.media_task_config import migrate_media_task_settings
from Backend.domain.config.media_concurrency import validate_media_concurrency
from Backend.domain.config.request_defaults import REQUEST_TIMEOUT_SECONDS


DEFAULT_TRANSCRIPTION_PROVIDER_ID = "bailian_asr"
DEFAULT_TRANSCRIPTION_PLATFORM = {
    "name": "百炼语音转录",
    "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "api_key": "", "model": "qwen-audio-3.1-asr-flash", "api_format": "DashScope",
    "request_timeout": REQUEST_TIMEOUT_SECONDS, "language_hints": [], "speaker_diarization_enabled": False,
    "chunk_duration_seconds": 240, "chunk_overlap_seconds": 2,
    "user_thread_counts": 3, "vad_threshold": 0.35,
}
LANGUAGE_HINTS = frozenset("zh en ja ko vi th id ms tl hi ar fr de es pt ru it nl sv da fi no el pl cs hu ro bg hr sk".split())
VOLCENGINE_LANGUAGES = {
    "zh": "zh-CN", "en": "en-US", "ja": "ja-JP", "id": "id-ID", "es": "es-MX",
    "pt": "pt-BR", "de": "de-DE", "fr": "fr-FR", "ko": "ko-KR", "tl": "fil-PH",
    "ms": "ms-MY", "th": "th-TH", "ar": "ar-SA", "it": "it-IT", "el": "el-GR",
    "nl": "nl-NL", "ru": "ru-RU", "vi": "vi-VN", "pl": "pl-PL", "ro": "ro-RO",
}
_OVERRIDE_FIELDS = frozenset({
    "provider_id", "api_url", "api_key", "model", "api_format", "request_timeout", "timeout",
    "app_id", "resource_id", "user_thread_counts",
    "language_hints", "speaker_diarization_enabled", "keep_dialect", "stream", "max_retries", "retranscribe",
    "chunk_duration_seconds", "chunk_overlap_seconds", "chunk_concurrency", "vad_threshold",
})


@dataclass(frozen=True)
class TranscriptionConfig:
    provider_id: str = DEFAULT_TRANSCRIPTION_PROVIDER_ID
    api_url: str = DEFAULT_TRANSCRIPTION_PLATFORM["api_url"]
    api_key: str = field(default="", repr=False)
    model: str = "qwen-audio-3.1-asr-flash"
    api_format: str = "DashScope"
    app_id: str = ""
    resource_id: str = ""
    request_timeout: float = REQUEST_TIMEOUT_SECONDS
    language_hints: tuple[str, ...] = ()
    speaker_diarization_enabled: bool = False
    keep_dialect: bool = False
    stream: bool = True
    max_retries: int = 0
    retranscribe: bool = False
    chunk_duration_seconds: int = 240
    chunk_overlap_seconds: float = 2
    user_thread_counts: int = 3
    vad_threshold: float = 0.35

    @classmethod
    def read_snapshot(cls) -> dict:
        """Read and complete legacy task values without writes or translation credentials."""
        from Backend.core.paths import config_path
        from Backend.infrastructure.config.store import ConfigStore

        result = {
            "transcription_platforms": {DEFAULT_TRANSCRIPTION_PROVIDER_ID: copy.deepcopy(DEFAULT_TRANSCRIPTION_PLATFORM)},
            "active_transcription_platform": DEFAULT_TRANSCRIPTION_PROVIDER_ID,
            "audio_translation_settings": {},
            "video_translation_settings": {},
        }
        from Backend.core.config import get_config_snapshot
        snapshot = get_config_snapshot()
        if snapshot is not None:
            for key in result:
                if key in snapshot:
                    result[key] = copy.deepcopy(snapshot[key])
            migrate_media_task_settings(result)
            return result
        try:
            with ConfigStore.CONFIG_FILE_LOCK:
                path = config_path()
                if path.exists():
                    with path.open("r", encoding="utf-8") as reader:
                        saved = json.load(reader)
                    if not isinstance(saved, dict):
                        raise ValueError("invalid root")
                    migrate_media_task_settings(saved)
                    for key in result:
                        if key in saved:
                            result[key] = copy.deepcopy(saved[key])
                migrate_media_task_settings(result)
        except (OSError, ValueError, TypeError) as error:
            raise PipelineError("ASR_CONFIG_ERROR", "无法读取转录接口配置", 400) from error
        return result

    def to_request_config(self) -> dict:
        result = asdict(self)
        result["language_hints"] = list(self.language_hints)
        result.pop("retranscribe")
        return result


def resolve_transcription_config(config=None, *, kind="audio") -> TranscriptionConfig:
    explicit_hints = isinstance(config, dict) and "language_hints" in config
    if isinstance(config, TranscriptionConfig):
        # Validate manually constructed objects as rigorously as API overrides.
        values = asdict(config)
    else:
        if config is None:
            config = {}
        if not isinstance(config, dict) or set(config) - _OVERRIDE_FIELDS:
            raise PipelineError("ASR_CONFIG_ERROR", "转录配置必须为仅包含支持字段的对象", 400)
        overrides = copy.deepcopy(config)
        if "chunk_concurrency" in overrides:
            legacy = overrides.pop("chunk_concurrency")
            if type(legacy) is not int or not 1 <= legacy <= 8:
                raise PipelineError("ASR_CONFIG_ERROR", "chunk_concurrency 必须为 1 至 8 的整数", 400)
            if "user_thread_counts" in overrides and overrides["user_thread_counts"] != legacy:
                raise PipelineError("ASR_CONFIG_ERROR", "chunk_concurrency 与 user_thread_counts 不一致", 400)
            overrides.setdefault("user_thread_counts", legacy)
        if "timeout" in overrides:
            if "request_timeout" in overrides and overrides["request_timeout"] != overrides["timeout"]:
                raise PipelineError("ASR_CONFIG_ERROR", "timeout 与 request_timeout 不一致", 400)
            overrides["request_timeout"] = overrides.pop("timeout")
        snapshot = TranscriptionConfig.read_snapshot()
        platforms = snapshot.get("transcription_platforms")
        provider_id = overrides.pop("provider_id", snapshot.get("active_transcription_platform"))
        if not isinstance(platforms, dict) or not isinstance(provider_id, str) or not provider_id.strip():
            raise PipelineError("ASR_CONFIG_ERROR", "请先选择转录接口", 400)
        platform = platforms.get(provider_id)
        if not isinstance(platform, dict):
            raise PipelineError("ASR_CONFIG_ERROR", "所选转录接口不存在", 400)
        values = asdict(TranscriptionConfig())
        # Saved timeouts are retired; only an explicit per-call override may change the default.
        values.update({key: copy.deepcopy(value) for key, value in platform.items()
                       if key in values and key not in {"provider_id", "request_timeout"}})
        task_settings = snapshot.get(f"{kind}_translation_settings")
        if not isinstance(task_settings, dict):
            raise PipelineError("ASR_CONFIG_ERROR", "音译设置必须为对象", 400)
        values.update({key: copy.deepcopy(value) for key, value in task_settings.items()
                       if key in ("language_hints", "speaker_diarization_enabled", "chunk_duration_seconds",
                                  "chunk_overlap_seconds", "vad_threshold")})
        values.update(overrides)
        values["provider_id"] = provider_id

    for key in ("api_url", "api_key", "model", "provider_id"):
        if not isinstance(values[key], str) or not values[key].strip():
            messages = {"api_key": "请配置转录接口 API Key", "api_url": "转录接口地址不能为空",
                        "model": "转录模型不能为空", "provider_id": "转录接口标识不能为空"}
            raise PipelineError("ASR_CONFIG_ERROR", messages[key], 400)
        values[key] = values[key].strip()
    try:
        url = urlsplit(values["api_url"])
        valid_url = url.scheme in ("http", "https") and url.hostname and not (url.username or url.password or url.query or url.fragment)
        _ = url.port
    except ValueError:
        valid_url = False
    if not valid_url or any(char in values["api_url"] for char in "\r\n"):
        raise PipelineError("ASR_CONFIG_ERROR", "转录接口必须为不含凭证或查询参数的 HTTP(S) 地址", 400)
    if any(char in values["api_key"] for char in "\r\n"):
        raise PipelineError("ASR_CONFIG_ERROR", "转录接口 API Key 格式无效", 400)
    formats = {"dashscope": "DashScope", "volcengineasrfast": "VolcengineASRFast"}
    api_format = values["api_format"]
    if not isinstance(api_format, str) or api_format.lower() not in formats:
        raise PipelineError("ASR_CONFIG_ERROR", "转录格式仅支持 DashScope 或 VolcengineASRFast", 400)
    values["api_format"] = formats[api_format.lower()]
    for key in ("app_id", "resource_id"):
        if not isinstance(values[key], str) or any(ord(char) < 32 for char in values[key]):
            raise PipelineError("ASR_CONFIG_ERROR", "火山应用 ID 和资源 ID 必须为单行文本", 400)
        values[key] = values[key].strip()
    if values["api_format"] == "VolcengineASRFast":
        expected_path = "/api/v3/auc/bigmodel/recognize/flash"
        if not url.path.rstrip("/").endswith(expected_path):
            raise PipelineError("ASR_CONFIG_ERROR", "火山接口地址与极速版协议不匹配", 400)
        values["api_url"] = values["api_url"].rstrip("/")
        if values["model"] != "bigmodel":
            raise PipelineError("ASR_CONFIG_ERROR", "火山录音识别的模型名称必须为 bigmodel", 400)
        values["resource_id"] = values["resource_id"] or "volc.bigasr.auc_turbo"
        if values["resource_id"] != "volc.bigasr.auc_turbo":
            raise PipelineError("ASR_CONFIG_ERROR", "火山资源 ID 与极速版协议不匹配", 400)
        if any(not values[key].isascii() or any(char.isspace() for char in values[key])
               for key in ("api_key", "app_id", "resource_id") if values[key]):
            raise PipelineError("ASR_CONFIG_ERROR", "火山鉴权与资源 ID 必须为不含空白的 ASCII 文本", 400)
    timeout = values["request_timeout"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise PipelineError("ASR_CONFIG_ERROR", "转录超时必须为 0 至 3600 秒之间的正数", 400)
    retries = values["max_retries"]
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 5:
        raise PipelineError("ASR_CONFIG_ERROR", "转录重试次数必须为 0 至 5 的整数", 400)
    for key in ("speaker_diarization_enabled", "keep_dialect", "stream", "retranscribe"):
        if not isinstance(values[key], bool):
            raise PipelineError("ASR_CONFIG_ERROR", "转录开关必须为布尔值", 400)
    hints = values["language_hints"]
    if not isinstance(hints, (list, tuple)) or len(hints) > 4 or any(not isinstance(hint, str) or hint not in LANGUAGE_HINTS for hint in hints):
        raise PipelineError("ASR_CONFIG_ERROR", "language_hints 最多包含 4 个受支持的语言代码", 400)
    values["language_hints"] = tuple(dict.fromkeys(hints))
    if values["api_format"] == "VolcengineASRFast":
        if explicit_hints and (len(hints) > 1 or any(hint not in VOLCENGINE_LANGUAGES for hint in hints)):
            raise PipelineError("ASR_CONFIG_ERROR", "火山录音识别只接受一种受支持的语言提示，例如 zh、en、ja；也可留空", 400)
    for key, lower, upper in (("chunk_duration_seconds", 30, 290),):
        value = values[key]
        if type(value) is not int or not lower <= value <= upper:
            raise PipelineError("ASR_CONFIG_ERROR", f"{key} 必须为 {lower} 至 {upper} 的整数", 400)
    for key, lower, upper in (("chunk_overlap_seconds", 0.5, 5), ("vad_threshold", 0.01, 0.99)):
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise PipelineError("ASR_CONFIG_ERROR", f"{key} 必须为 {lower} 至 {upper} 之间的数字", 400)
    try:
        validate_media_concurrency(values["user_thread_counts"])
    except ValueError as error:
        raise PipelineError("ASR_CONFIG_ERROR", str(error), 400) from None
    return TranscriptionConfig(**values)


def validate_transcription_platform(identifier: str, platform: dict) -> None:
    """验证单个转录平台配置项，抛出 ValueError 表示配置非法。"""
    if not isinstance(identifier, str) or not isinstance(platform, dict):
        raise ValueError("转录接口配置必须使用字符串 ID 和 JSON 对象")
    for field in ("name", "api_url", "api_key", "model", "api_format"):
        if field in platform and not isinstance(platform[field], str):
            raise ValueError(f"转录接口字段 {field} 必须是字符串")
    for field in ("app_id", "resource_id"):
        value = platform.get(field, "")
        if not isinstance(value, str) or any(c in value for c in "\r\n\x00"):
            raise ValueError(f"转录接口字段 {field} 必须是单行文本")
    if "language_hints" in platform and (not isinstance(platform["language_hints"], list)
            or any(not isinstance(value, str) for value in platform["language_hints"])):
        raise ValueError("转录接口字段 language_hints 必须是字符串列表")
    if "speaker_diarization_enabled" in platform and not isinstance(platform["speaker_diarization_enabled"], bool):
        raise ValueError("转录接口字段 speaker_diarization_enabled 必须是布尔值")
    validate_media_concurrency(platform.get("user_thread_counts", 3))
    for field in ("chunk_duration_seconds",):
        if field in platform and type(platform[field]) is not int:
            raise ValueError(f"转录接口字段 {field} 必须是整数")
    for field in ("chunk_overlap_seconds", "vad_threshold"):
        if field in platform and (isinstance(platform[field], bool) or not isinstance(platform[field], (int, float))):
            raise ValueError(f"转录接口字段 {field} 必须是数字")
